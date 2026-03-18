import logging

from django.db import OperationalError, ProgrammingError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from booking.models import Booking, BookingTransaction
from apps.notification.models import Notification, PartnerNotification
from payment.models import PlumTransaction
from property.models import Property, PropertyPrice
from users.models.clients import Client
from users.models.partners import Partner

from .sync import (
    ensure_booking_status_history,
    upsert_booking_from_booking,
    upsert_booking_payment_link_from_booking_transaction,
    upsert_customer_from_client,
    upsert_from_client_notification,
    upsert_from_partner_notification,
    upsert_partner_from_partner,
    upsert_payment_transaction_from_plum_transaction,
    upsert_property_from_property,
    upsert_property_price_from_property_price,
)

logger = logging.getLogger(__name__)


def _safe_run(label, fn):
    try:
        fn()
    except (ProgrammingError, OperationalError) as exc:
        logger.warning(
            "normalized sync skipped (%s): table or schema unavailable: %s",
            label,
            exc,
        )
    except Exception:
        logger.exception("normalized sync failed (%s)", label)


@receiver(post_save, sender=Client)
def sync_customer(sender, instance: Client, **kwargs):
    _safe_run("customer", lambda: upsert_customer_from_client(instance))


@receiver(post_save, sender=Partner)
def sync_partner(sender, instance: Partner, **kwargs):
    _safe_run("partner", lambda: upsert_partner_from_partner(instance))


@receiver(post_save, sender=Property)
def sync_property(sender, instance: Property, **kwargs):
    _safe_run("property", lambda: upsert_property_from_property(instance))


@receiver(post_save, sender=PropertyPrice)
def sync_property_price(sender, instance: PropertyPrice, **kwargs):
    _safe_run("property_price", lambda: upsert_property_price_from_property_price(instance))


@receiver(pre_save, sender=Booking)
def cache_previous_booking_status(sender, instance: Booking, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    previous_status = (
        Booking.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )
    instance._previous_status = previous_status


@receiver(post_save, sender=Booking)
def sync_booking(sender, instance: Booking, created: bool, **kwargs):
    def _sync():
        upsert_booking_from_booking(instance)
        previous_status = None if created else getattr(instance, "_previous_status", None)
        status_changed = created or previous_status != instance.status
        if status_changed:
            ensure_booking_status_history(instance, from_status=previous_status)

    _safe_run("booking", _sync)


@receiver(post_save, sender=PlumTransaction)
def sync_payment(sender, instance: PlumTransaction, **kwargs):
    _safe_run("payment", lambda: upsert_payment_transaction_from_plum_transaction(instance))


@receiver(post_save, sender=BookingTransaction)
def sync_booking_payment_link(sender, instance: BookingTransaction, **kwargs):
    _safe_run(
        "booking_payment_link",
        lambda: upsert_booking_payment_link_from_booking_transaction(instance),
    )


@receiver(post_save, sender=Notification)
def sync_client_notification(sender, instance: Notification, **kwargs):
    _safe_run("client_notification", lambda: upsert_from_client_notification(instance))


@receiver(post_save, sender=PartnerNotification)
def sync_partner_notification(sender, instance: PartnerNotification, **kwargs):
    _safe_run("partner_notification", lambda: upsert_from_partner_notification(instance))
