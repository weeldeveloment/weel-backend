import logging

from firebase_admin import messaging
from django.db.utils import ProgrammingError

from users.models import Client
from users.models.partners import Partner
from .models import Notification


logger = logging.getLogger(__name__)


class FCMService:
    @staticmethod
    def _deactivate_invalid_tokens(tokens: list[str]):
        if not tokens:
            return

        from users.models.clients import ClientDevice
        from users.models.partners import PartnerDevice
        try:
            ClientDevice.objects.filter(fcm_token__in=tokens, is_active=True).update(
                is_active=False
            )
            PartnerDevice.objects.filter(fcm_token__in=tokens, is_active=True).update(
                is_active=False
            )
        except ProgrammingError as exc:
            logger.error("Skipping invalid token deactivation due to missing table: %s", exc)

    @staticmethod
    def send_to_tokens(
        tokens: list[str], title: str, body: str, data: dict | None = None
    ):
        if not tokens:
            logger.info("FCM skipped: empty token list")
            return None

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message)

        invalid_tokens: list[str] = []
        for idx, send_response in enumerate(response.responses):
            if send_response.success:
                continue

            token = tokens[idx] if idx < len(tokens) else "unknown"
            error_code = getattr(getattr(send_response, "exception", None), "code", None)
            error_message = str(getattr(send_response, "exception", "Unknown error"))

            logger.warning(
                "FCM token delivery failed. token=%s code=%s error=%s",
                token,
                error_code,
                error_message,
            )

            if error_code in {
                "registration-token-not-registered",
                "invalid-registration-token",
                "invalid-argument",
                "unregistered",
            }:
                invalid_tokens.append(token)

        if invalid_tokens:
            FCMService._deactivate_invalid_tokens(invalid_tokens)
            logger.info("FCM invalid tokens deactivated: count=%s", len(invalid_tokens))

        logger.info(
            "FCM info",
            extra={
                "success": response.success_count,
                "failure": response.failure_count,
                "tokens_total": len(tokens),
            },
        )
        return response


class NotificationService:
    @staticmethod
    def _normalize_data(data: dict | None) -> dict:
        if not data:
            return {}
        normalized: dict[str, str] = {}
        for key, value in data.items():
            if value is None:
                continue
            normalized[str(key)] = str(value)
        return normalized

    @staticmethod
    def send_to_client(
        client: Client,
        title: str,
        message: str,
        notification_type: str,
        data: dict | None = None,
    ):
        notification = Notification.objects.create(
            recipient=client,
            title=title,
            push_message=message,
            notification_type=notification_type,
            status=Notification.Status.PENDING,
            is_for_every_one=False,
        )

        try:
            tokens = list(
                client.devices.filter(is_active=True).values_list("fcm_token", flat=True),
            )
        except ProgrammingError as exc:
            logger.error("Unable to load client device tokens due to database schema mismatch: %s", exc)
            tokens = []

        response = FCMService.send_to_tokens(
            tokens=tokens,
            title=title,
            body=message,
            data=NotificationService._normalize_data(data),
        )

        if response and response.success_count > 0:
            notification.status = Notification.Status.SENT
            notification.save(update_fields=["status"])
        else:
            logger.warning(
                "Notification remains pending: no successful FCM delivery. recipient=%s",
                getattr(client, "id", None),
            )

        return notification

    @staticmethod
    def send_to_partner(
        partner: Partner,
        title: str,
        message: str,
        data: dict | None = None,
    ):
        try:
            tokens = list(
                partner.devices.filter(is_active=True).values_list("fcm_token", flat=True),
            )
        except ProgrammingError as exc:
            logger.error("Unable to load partner device tokens due to database schema mismatch: %s", exc)
            tokens = []

        return FCMService.send_to_tokens(
            tokens=tokens,
            title=title,
            body=message,
            data=NotificationService._normalize_data(data),
        )

    @staticmethod
    def send_broadcast(notification: Notification):
        message = messaging.send(
            messaging.Message(
                topic="all_clients",
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.push_message,
                ),
                data={
                    "type": "system",
                },
            )
        )
        logger.info("Response: %s", message)
        notification.status = Notification.Status.SENT
        notification.save(update_fields=["status"])
