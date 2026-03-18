from django.core.management.base import BaseCommand

from booking.models import Booking, BookingTransaction
from apps.notification.models import Notification, PartnerNotification
from payment.models import PlumTransaction
from property.models import Property, PropertyPrice
from users.models.clients import Client
from users.models.partners import Partner

from normalized.sync import (
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


class Command(BaseCommand):
    help = "Backfill shadow normalized tables from legacy tables (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=1000,
            help="Iterator chunk size.",
        )

    def handle(self, *args, **options):
        chunk_size = options["chunk_size"]

        self.stdout.write("Starting normalized backfill...")
        self._sync_queryset("clients", Client.objects.all(), upsert_customer_from_client, chunk_size)
        self._sync_queryset("partners", Partner.objects.all(), upsert_partner_from_partner, chunk_size)
        self._sync_queryset("properties", Property.objects.all(), upsert_property_from_property, chunk_size)
        self._sync_queryset(
            "property_prices",
            PropertyPrice.objects.select_related("property").all(),
            upsert_property_price_from_property_price,
            chunk_size,
        )
        self._sync_queryset(
            "plum_transactions",
            PlumTransaction.objects.all(),
            upsert_payment_transaction_from_plum_transaction,
            chunk_size,
        )
        self._sync_queryset(
            "bookings",
            Booking.objects.select_related("client", "property").all(),
            upsert_booking_from_booking,
            chunk_size,
        )
        self._sync_queryset(
            "booking_status_history",
            Booking.objects.select_related("client", "property").all(),
            lambda booking: ensure_booking_status_history(booking, from_status=None, source="backfill"),
            chunk_size,
        )
        self._sync_queryset(
            "booking_transactions",
            BookingTransaction.objects.select_related("booking", "plum_transaction").all(),
            upsert_booking_payment_link_from_booking_transaction,
            chunk_size,
        )
        self._sync_queryset(
            "notifications",
            Notification.objects.select_related("recipient").all(),
            upsert_from_client_notification,
            chunk_size,
        )
        self._sync_queryset(
            "partner_notifications",
            PartnerNotification.objects.select_related("partner").all(),
            upsert_from_partner_notification,
            chunk_size,
        )
        self.stdout.write(self.style.SUCCESS("Normalized backfill complete."))

    def _sync_queryset(self, label, queryset, sync_fn, chunk_size):
        total = 0
        for obj in queryset.iterator(chunk_size=chunk_size):
            sync_fn(obj)
            total += 1
        self.stdout.write(f"- {label}: {total}")
