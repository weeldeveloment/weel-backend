from django.db import models
from django.utils.translation import gettext_lazy as _

from shared.models import HardDeleteBaseModel


class Customer(HardDeleteBaseModel):
    legacy_client_id = models.BigIntegerField(unique=True, db_index=True)
    legacy_client_guid = models.UUIDField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=16, db_index=True)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "norm_customers"
        verbose_name = _("Normalized customer")
        verbose_name_plural = _("Normalized customers")


class Partner(HardDeleteBaseModel):
    legacy_partner_id = models.BigIntegerField(unique=True, db_index=True)
    legacy_partner_guid = models.UUIDField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, db_index=True)
    phone_number = models.CharField(max_length=16, db_index=True)
    email = models.EmailField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_default=True)
    is_verified = models.BooleanField(default=False, db_default=False)
    verified_by_admin_id = models.IntegerField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "norm_partners"
        verbose_name = _("Normalized partner")
        verbose_name_plural = _("Normalized partners")


class Property(HardDeleteBaseModel):
    legacy_property_id = models.BigIntegerField(unique=True, db_index=True)
    legacy_property_guid = models.UUIDField(unique=True)
    partner = models.ForeignKey(
        Partner,
        on_delete=models.PROTECT,
        related_name="properties",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=75)
    currency = models.CharField(max_length=3)
    verification_status = models.CharField(max_length=10)
    is_verified = models.BooleanField(default=False, db_default=False)
    is_archived = models.BooleanField(default=False, db_default=False)
    region_id = models.BigIntegerField(null=True, blank=True)
    district_id = models.BigIntegerField(null=True, blank=True)
    shaharcha_id = models.BigIntegerField(null=True, blank=True)
    mahalla_id = models.BigIntegerField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=17, decimal_places=14, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=17, decimal_places=14, null=True, blank=True
    )

    class Meta:
        db_table = "norm_properties"
        verbose_name = _("Normalized property")
        verbose_name_plural = _("Normalized properties")


class PropertyPrice(HardDeleteBaseModel):
    legacy_property_price_id = models.BigIntegerField(unique=True, db_index=True)
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="prices"
    )
    month_from = models.DateField()
    month_to = models.DateField()
    price_per_person = models.DecimalField(max_digits=12, decimal_places=2)
    price_on_working_days = models.DecimalField(max_digits=12, decimal_places=2)
    price_on_weekends = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "norm_property_prices"
        verbose_name = _("Normalized property price")
        verbose_name_plural = _("Normalized property prices")
        constraints = [
            models.CheckConstraint(
                check=models.Q(month_to__gte=models.F("month_from")),
                name="norm_property_price_valid_range",
            )
        ]


class Booking(HardDeleteBaseModel):
    legacy_booking_id = models.BigIntegerField(unique=True, db_index=True)
    legacy_booking_guid = models.UUIDField(unique=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True
    )
    property = models.ForeignKey(
        Property, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True
    )
    booking_number = models.CharField(max_length=7, unique=True)
    check_in = models.DateField()
    check_out = models.DateField()
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    babies = models.PositiveSmallIntegerField(default=0)
    current_status = models.CharField(max_length=20, db_index=True)
    cancellation_reason = models.CharField(max_length=100, null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False, db_default=False)
    payment_reminder_stage = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        db_table = "norm_bookings"
        verbose_name = _("Normalized booking")
        verbose_name_plural = _("Normalized bookings")
        constraints = [
            models.CheckConstraint(
                check=models.Q(check_out__gt=models.F("check_in")),
                name="norm_booking_check_out_after_check_in",
            )
        ]


class BookingStatusHistory(HardDeleteBaseModel):
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="status_history"
    )
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20, db_index=True)
    reason = models.CharField(max_length=100, null=True, blank=True)
    source = models.CharField(max_length=32, default="legacy_sync")
    changed_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "norm_booking_status_history"
        verbose_name = _("Normalized booking status history")
        verbose_name_plural = _("Normalized booking status history")
        indexes = [
            models.Index(fields=["booking", "changed_at"], name="norm_booking_hist_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "to_status", "changed_at", "source"],
                name="norm_booking_status_history_uniq",
            )
        ]


class PaymentTransaction(HardDeleteBaseModel):
    legacy_plum_transaction_id = models.BigIntegerField(unique=True, db_index=True)
    legacy_plum_transaction_guid = models.UUIDField(unique=True)
    provider_transaction_id = models.CharField(max_length=255, unique=True)
    provider_hold_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=4)
    status = models.CharField(max_length=20)
    card_id = models.CharField(max_length=255, null=True, blank=True)
    extra_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "norm_payment_transactions"
        verbose_name = _("Normalized payment transaction")
        verbose_name_plural = _("Normalized payment transactions")


class BookingPaymentLink(HardDeleteBaseModel):
    legacy_booking_transaction_id = models.BigIntegerField(unique=True, db_index=True)
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="payment_links"
    )
    payment_transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.PROTECT,
        related_name="booking_links",
    )

    class Meta:
        db_table = "norm_booking_payment_links"
        verbose_name = _("Normalized booking payment link")
        verbose_name_plural = _("Normalized booking payment links")


class Notification(HardDeleteBaseModel):
    legacy_notification_id = models.BigIntegerField(
        unique=True, null=True, blank=True, db_index=True
    )
    legacy_partner_notification_id = models.BigIntegerField(
        unique=True, null=True, blank=True, db_index=True
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    notification_type = models.CharField(max_length=30)
    status = models.CharField(max_length=15)
    is_broadcast = models.BooleanField(default=False, db_default=False)
    is_read = models.BooleanField(default=False, db_default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "norm_notifications"
        verbose_name = _("Normalized notification")
        verbose_name_plural = _("Normalized notifications")
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        is_broadcast=True,
                        customer__isnull=True,
                        partner__isnull=True,
                    )
                    | models.Q(
                        is_broadcast=False,
                        customer__isnull=False,
                        partner__isnull=True,
                    )
                    | models.Q(
                        is_broadcast=False,
                        customer__isnull=True,
                        partner__isnull=False,
                    )
                ),
                name="norm_notification_recipient_consistency",
            )
        ]


class ExchangeRate(HardDeleteBaseModel):
    legacy_exchange_rate_id = models.BigIntegerField(unique=True, db_index=True)
    currency = models.CharField(max_length=3, db_index=True)
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    date = models.DateField(db_index=True)

    class Meta:
        db_table = "norm_exchange_rates"
        verbose_name = _("Normalized exchange rate")
        verbose_name_plural = _("Normalized exchange rates")
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "date"],
                name="norm_exchange_rate_currency_date_uniq",
            )
        ]


class ClientDevice(HardDeleteBaseModel):
    legacy_client_device_id = models.BigIntegerField(unique=True, db_index=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="devices",
        null=True,
        blank=True,
    )
    fcm_token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "norm_client_devices"
        verbose_name = _("Normalized client device")
        verbose_name_plural = _("Normalized client devices")
        indexes = [
            models.Index(
                fields=["customer", "device_type", "is_active"],
                name="norm_client_dev_lookup_idx",
            ),
        ]


class PartnerDevice(HardDeleteBaseModel):
    legacy_partner_device_id = models.BigIntegerField(unique=True, db_index=True)
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name="devices",
        null=True,
        blank=True,
    )
    fcm_token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "norm_partner_devices"
        verbose_name = _("Normalized partner device")
        verbose_name_plural = _("Normalized partner devices")
        indexes = [
            models.Index(
                fields=["partner", "device_type", "is_active"],
                name="norm_partner_dev_lookup_idx",
            ),
        ]


class ClientSession(HardDeleteBaseModel):
    legacy_client_session_id = models.BigIntegerField(unique=True, db_index=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        related_name="sessions",
        null=True,
        blank=True,
    )
    device_id = models.CharField(max_length=255, null=True, blank=True)
    user_agent = models.CharField(max_length=1024, blank=True, default="")
    last_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "norm_client_sessions"
        verbose_name = _("Normalized client session")
        verbose_name_plural = _("Normalized client sessions")
        indexes = [
            models.Index(fields=["customer", "created_at"], name="norm_client_sess_idx"),
        ]


class PartnerSession(HardDeleteBaseModel):
    legacy_partner_session_id = models.BigIntegerField(unique=True, db_index=True)
    partner = models.ForeignKey(
        Partner,
        on_delete=models.SET_NULL,
        related_name="sessions",
        null=True,
        blank=True,
    )
    device_id = models.CharField(max_length=255, null=True, blank=True)
    user_agent = models.CharField(max_length=1024, blank=True, default="")
    last_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "norm_partner_sessions"
        verbose_name = _("Normalized partner session")
        verbose_name_plural = _("Normalized partner sessions")
        indexes = [
            models.Index(fields=["partner", "created_at"], name="norm_partner_sess_idx"),
        ]
