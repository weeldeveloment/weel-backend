from django.urls import path

from .views import FCMTokenUpdateView, PartnerFCMTokenUpdateView

urlpatterns = [
    path("device/", FCMTokenUpdateView.as_view(), name="update-fcm-token"),
    path(
        "partner/device/",
        PartnerFCMTokenUpdateView.as_view(),
        name="update-partner-fcm-token",
    ),
]
