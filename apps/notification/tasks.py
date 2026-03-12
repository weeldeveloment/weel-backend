from datetime import timedelta

from celery import shared_task

from django.utils import timezone

from booking.models import Booking
from .models import Notification
from .service import NotificationService


@shared_task
def send_booking_reminders():
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    bookings = Booking.objects.filter(
        check_in=tomorrow,
        reminder_sent=False,
        status=Booking.BookingStatus.CONFIRMED,
    ).select_related("client", "property")

    for booking in bookings:
        NotificationService.send_to_client(
            client=booking.client,
            title="Напоминание о предстоящем бронирование⏰",
            message=(
                f"Напоминаем, что заселение по вашему бронированию "
                f"в {booking.property.title} состоится затвра"
                f"Желаем приятного пребывания!"
            ),
            notification_type=Notification.NotificationType.REMINDER,
            data={"booking_id": str(booking.guid)},
        )

        booking.reminder_sent = True
        booking.save(update_fields=["reminder_sent"])
