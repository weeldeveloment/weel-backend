from django.db import models
from django.utils.translation import gettext_lazy as _

from shared.models import HardDeleteBaseModel
from users.models.clients import Client

# Create your models here.


class Notification(HardDeleteBaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        SENT = "sent", _("Sent")

    class NotificationType(models.TextChoices):
        BOOKING_CONFIRMED = "booking_confirmed", _("Booking confirmed")
        BOOKING_CANCELLED = "booking_cancelled", _("Booking cancelled")
        REMINDER = "reminder", _("Reminder")
        SYSTEM = "system", _("System")

    recipient = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, null=True, verbose_name=_("Title"))
    push_message = models.TextField(null=True, verbose_name=_("Push message"))
    notification_type = models.CharField(
        choices=NotificationType,
        max_length=20,
    )
    status = models.CharField(
        max_length=15,
        choices=Status,
        default=Status.PENDING,
        verbose_name=_("Status"),
    )
    is_for_every_one = models.BooleanField(
        default=False, verbose_name=_("Is for everyone")
    )

    class Meta:
        db_table = "notifications"
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        constraints = [
            models.CheckConstraint(
                check=models.Q(is_for_every_one=True, recipient__isnull=True)
                | models.Q(is_for_every_one=False, recipient__isnull=False),
                name="notification_recipient_consistency",
            )
        ]

    def __str__(self):
        return f"Recipient: {self.recipient_id} | Title: {self.title} | Push message: {self.push_message}"

    def __repr__(self):
        return f"<Recipient={self.id} title={self.title}> push_message={self.push_message} notification_type={self.notification_type}"