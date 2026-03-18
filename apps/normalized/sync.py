from __future__ import annotations

from typing import Optional

from django.utils import timezone

from booking.models import Booking as LegacyBooking
from booking.models import BookingTransaction as LegacyBookingTransaction
from apps.notification.models import (
    Notification as LegacyNotification,
    PartnerNotification as LegacyPartnerNotification,
)
from payment.models import PlumTransaction as LegacyPlumTransaction
from property.models import Property as LegacyProperty
from property.models import PropertyPrice as LegacyPropertyPrice
from users.models.clients import Client as LegacyClient
from users.models.partners import Partner as LegacyPartner

from . import models


def upsert_customer_from_client(client: LegacyClient) -> models.Customer:
    defaults = {
        "guid": client.guid,
        "legacy_client_guid": client.guid,
        "first_name": client.first_name,
        "last_name": client.last_name,
        "phone_number": client.phone_number,
        "is_active": client.is_active,
    }
    customer, _ = models.Customer.objects.update_or_create(
        legacy_client_id=client.id,
        defaults=defaults,
    )
    return customer


def upsert_partner_from_partner(partner: LegacyPartner) -> models.Partner:
    defaults = {
        "guid": partner.guid,
        "legacy_partner_guid": partner.guid,
        "first_name": partner.first_name,
        "last_name": partner.last_name,
        "username": partner.username,
        "phone_number": partner.phone_number,
        "email": partner.email,
        "is_active": partner.is_active,
        "is_verified": bool(partner.is_verified),
        "verified_by_admin_id": partner.verified_by_id,
        "verified_at": partner.verified_at,
    }
    normalized_partner, _ = models.Partner.objects.update_or_create(
        legacy_partner_id=partner.id,
        defaults=defaults,
    )
    return normalized_partner


def upsert_property_from_property(property_obj: LegacyProperty) -> models.Property:
    normalized_partner = None
    if property_obj.partner_id:
        normalized_partner = upsert_partner_from_partner(property_obj.partner)

    location = getattr(property_obj, "property_location", None)

    defaults = {
        "guid": property_obj.guid,
        "legacy_property_guid": property_obj.guid,
        "partner": normalized_partner,
        "title": property_obj.title,
        "currency": property_obj.currency,
        "verification_status": property_obj.verification_status,
        "is_verified": bool(property_obj.is_verified),
        "is_archived": bool(property_obj.is_archived),
        "region_id": property_obj.region_id,
        "district_id": property_obj.district_id,
        "shaharcha_id": property_obj.shaharcha_id,
        "mahalla_id": property_obj.mahalla_id,
        "city": getattr(location, "city", None),
        "country": getattr(location, "country", None),
        "latitude": getattr(location, "latitude", None),
        "longitude": getattr(location, "longitude", None),
    }
    normalized_property, _ = models.Property.objects.update_or_create(
        legacy_property_id=property_obj.id,
        defaults=defaults,
    )
    return normalized_property


def upsert_property_price_from_property_price(
    price_obj: LegacyPropertyPrice,
) -> models.PropertyPrice:
    normalized_property = upsert_property_from_property(price_obj.property)
    defaults = {
        "guid": price_obj.guid,
        "property": normalized_property,
        "month_from": price_obj.month_from,
        "month_to": price_obj.month_to,
        "price_per_person": price_obj.price_per_person,
        "price_on_working_days": price_obj.price_on_working_days,
        "price_on_weekends": price_obj.price_on_weekends,
    }
    normalized_price, _ = models.PropertyPrice.objects.update_or_create(
        legacy_property_price_id=price_obj.id,
        defaults=defaults,
    )
    return normalized_price


def upsert_booking_from_booking(booking: LegacyBooking) -> models.Booking:
    normalized_customer = upsert_customer_from_client(booking.client)
    normalized_property = upsert_property_from_property(booking.property)

    defaults = {
        "guid": booking.guid,
        "legacy_booking_guid": booking.guid,
        "customer": normalized_customer,
        "property": normalized_property,
        "booking_number": booking.booking_number,
        "check_in": booking.check_in,
        "check_out": booking.check_out,
        "adults": booking.adults,
        "children": booking.children,
        "babies": booking.babies,
        "current_status": booking.status,
        "cancellation_reason": booking.cancellation_reason,
        "confirmed_at": booking.confirmed_at,
        "cancelled_at": booking.cancelled_at,
        "completed_at": booking.completed_at,
        "reminder_sent": booking.reminder_sent,
        "payment_reminder_stage": booking.payment_reminder_stage,
    }
    normalized_booking, _ = models.Booking.objects.update_or_create(
        legacy_booking_id=booking.id,
        defaults=defaults,
    )
    return normalized_booking


def _status_changed_at(booking: LegacyBooking) -> timezone.datetime:
    if (
        booking.status == LegacyBooking.BookingStatus.CONFIRMED
        and booking.confirmed_at is not None
    ):
        return booking.confirmed_at
    if (
        booking.status == LegacyBooking.BookingStatus.CANCELLED
        and booking.cancelled_at is not None
    ):
        return booking.cancelled_at
    if (
        booking.status == LegacyBooking.BookingStatus.COMPLETED
        and booking.completed_at is not None
    ):
        return booking.completed_at
    if booking.status == LegacyBooking.BookingStatus.PENDING:
        return booking.created_at
    return booking.updated_at


def ensure_booking_status_history(
    booking: LegacyBooking, from_status: Optional[str], source: str = "legacy_sync"
) -> models.BookingStatusHistory:
    normalized_booking = upsert_booking_from_booking(booking)
    changed_at = _status_changed_at(booking)
    history, _ = models.BookingStatusHistory.objects.get_or_create(
        booking=normalized_booking,
        to_status=booking.status,
        changed_at=changed_at,
        source=source,
        defaults={
            "from_status": from_status,
            "reason": booking.cancellation_reason,
        },
    )
    return history


def upsert_payment_transaction_from_plum_transaction(
    transaction: LegacyPlumTransaction,
) -> models.PaymentTransaction:
    defaults = {
        "guid": transaction.guid,
        "legacy_plum_transaction_guid": transaction.guid,
        "provider_transaction_id": transaction.transaction_id,
        "provider_hold_id": transaction.hold_id,
        "amount": transaction.amount,
        "type": transaction.type,
        "status": transaction.status,
        "card_id": transaction.card_id,
        "extra_id": transaction.extra_id,
    }
    payment, _ = models.PaymentTransaction.objects.update_or_create(
        legacy_plum_transaction_id=transaction.id,
        defaults=defaults,
    )
    return payment


def upsert_booking_payment_link_from_booking_transaction(
    link: LegacyBookingTransaction,
) -> models.BookingPaymentLink:
    normalized_booking = upsert_booking_from_booking(link.booking)
    normalized_payment = upsert_payment_transaction_from_plum_transaction(
        link.plum_transaction
    )
    defaults = {
        "guid": link.guid,
        "booking": normalized_booking,
        "payment_transaction": normalized_payment,
    }
    normalized_link, _ = models.BookingPaymentLink.objects.update_or_create(
        legacy_booking_transaction_id=link.id,
        defaults=defaults,
    )
    return normalized_link


def upsert_from_client_notification(
    notification: LegacyNotification,
) -> models.Notification:
    normalized_customer = None
    if notification.recipient_id:
        normalized_customer = upsert_customer_from_client(notification.recipient)

    defaults = {
        "guid": notification.guid,
        "customer": normalized_customer,
        "partner": None,
        "title": notification.title,
        "body": notification.push_message,
        "notification_type": notification.notification_type,
        "status": notification.status,
        "is_broadcast": notification.is_for_every_one,
        "is_read": False,
        "read_at": None,
        "payload": {},
    }
    normalized_notification, _ = models.Notification.objects.update_or_create(
        legacy_notification_id=notification.id,
        defaults=defaults,
    )
    return normalized_notification


def upsert_from_partner_notification(
    notification: LegacyPartnerNotification,
) -> models.Notification:
    normalized_partner = upsert_partner_from_partner(notification.partner)
    defaults = {
        "guid": notification.guid,
        "customer": None,
        "partner": normalized_partner,
        "title": notification.title,
        "body": notification.body,
        "notification_type": notification.notification_type,
        "status": "sent",
        "is_broadcast": False,
        "is_read": notification.is_read,
        "read_at": notification.read_at,
        "payload": notification.data or {},
    }
    normalized_notification, _ = models.Notification.objects.update_or_create(
        legacy_partner_notification_id=notification.id,
        defaults=defaults,
    )
    return normalized_notification
