import logging
import os

from firebase_admin import messaging
from django.db.utils import ProgrammingError

from users.models import Client
from users.models.partners import Partner
from .models import Notification, PartnerNotification


logger = logging.getLogger(__name__)


def _mask_token(token: str | None) -> str:
    if not token:
        return "unknown"
    if len(token) <= 12:
        return token
    return f"{token[:8]}...{token[-4:]}"


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
        normalized_data = data or {}
        if not tokens:
            logger.info(
                "FCM skipped: empty token list. title=%s data_keys=%s",
                title,
                sorted(normalized_data.keys()),
            )
            return None

        logger.info(
            "FCM send started. title=%s tokens_total=%s data_keys=%s token_previews=%s",
            title,
            len(tokens),
            sorted(normalized_data.keys()),
            [_mask_token(token) for token in tokens],
        )

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=normalized_data,
            tokens=tokens,
        )
        try:
            response = messaging.send_each_for_multicast(message)
        except Exception:
            logger.exception(
                "FCM send failed before per-token response. title=%s tokens_total=%s data_keys=%s credentials_path=%s",
                title,
                len(tokens),
                sorted(normalized_data.keys()),
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            )
            raise

        invalid_tokens: list[str] = []
        for idx, send_response in enumerate(response.responses):
            if send_response.success:
                logger.info(
                    "FCM token delivery succeeded. token=%s",
                    _mask_token(tokens[idx] if idx < len(tokens) else "unknown"),
                )
                continue

            token = tokens[idx] if idx < len(tokens) else "unknown"
            error_code = getattr(getattr(send_response, "exception", None), "code", None)
            error_message = str(getattr(send_response, "exception", "Unknown error"))

            logger.warning(
                "FCM token delivery failed. token=%s code=%s error=%s",
                _mask_token(token),
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
            "FCM send finished. title=%s success=%s failure=%s tokens_total=%s invalidated=%s",
            title,
            response.success_count,
            response.failure_count,
            len(tokens),
            len(invalid_tokens),
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
        normalized_data = NotificationService._normalize_data(data)

        logger.info(
            "Client notification requested. client_id=%s notification_type=%s title=%s data_keys=%s",
            getattr(client, "id", None),
            notification_type,
            title,
            sorted(normalized_data.keys()),
        )

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

        logger.info(
            "Client notification tokens loaded. client_id=%s tokens_total=%s",
            getattr(client, "id", None),
            len(tokens),
        )

        response = FCMService.send_to_tokens(
            tokens=tokens,
            title=title,
            body=message,
            data=normalized_data,
        )

        if response and response.success_count > 0:
            notification.status = Notification.Status.SENT
            notification.save(update_fields=["status"])
            logger.info(
                "Client notification marked sent. client_id=%s notification_id=%s success=%s failure=%s",
                getattr(client, "id", None),
                getattr(notification, "id", None),
                response.success_count,
                response.failure_count,
            )
        else:
            logger.warning(
                "Notification remains pending: no successful FCM delivery. client_id=%s notification_id=%s",
                getattr(client, "id", None),
                getattr(notification, "id", None),
            )

        return notification

    @staticmethod
    def send_to_partner(
        partner: Partner,
        title: str,
        message: str,
        notification_type: str = "system",
        data: dict | None = None,
    ):
        """Send notification to partner and save to history"""
        normalized_data = NotificationService._normalize_data(data)
        logger.info(
            "Partner notification requested. partner_id=%s notification_type=%s title=%s data_keys=%s",
            getattr(partner, "id", None),
            notification_type,
            title,
            sorted(normalized_data.keys()),
        )

        # Save to notification history
        try:
            PartnerNotification.objects.create(
                partner=partner,
                title=title,
                body=message,
                notification_type=notification_type,
                data=data or {},
                is_read=False,
            )
            logger.info(
                "Partner notification saved to history. partner=%s title=%s",
                getattr(partner, "id", None),
                title,
            )
        except Exception as exc:
            logger.error(
                "Failed to save partner notification to history: %s",
                exc,
            )

        # Send push notification
        try:
            tokens = list(
                partner.devices.filter(is_active=True).values_list("fcm_token", flat=True),
            )
        except ProgrammingError as exc:
            logger.error("Unable to load partner device tokens due to database schema mismatch: %s", exc)
            tokens = []

        logger.info(
            "Partner notification tokens loaded. partner_id=%s tokens_total=%s",
            getattr(partner, "id", None),
            len(tokens),
        )

        response = FCMService.send_to_tokens(
            tokens=tokens,
            title=title,
            body=message,
            data=normalized_data,
        )
        if response:
            logger.info(
                "Partner notification send result. partner_id=%s success=%s failure=%s",
                getattr(partner, "id", None),
                response.success_count,
                response.failure_count,
            )
        else:
            logger.warning(
                "Partner notification send skipped or produced no response. partner_id=%s",
                getattr(partner, "id", None),
            )
        return response

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
