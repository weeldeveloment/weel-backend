from unittest.mock import patch
import uuid

from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework import status

from admin_auth.authentication import create_admin_tokens
from users.models.partners import Partner


User = get_user_model()


class ChatPushNotificationTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"is_staff": True, "is_active": True},
        )
        if not self.admin.is_staff or not self.admin.is_active:
            self.admin.is_staff = True
            self.admin.is_active = True
            self.admin.save(update_fields=["is_staff", "is_active"])
        phone_suffix = uuid.uuid4().int % 10**7
        self.partner = Partner.objects.create(
            first_name="Test",
            last_name="Partner",
            username=f"partner_{uuid.uuid4().hex[:8]}",
            phone_number=f"+99890{phone_suffix:07d}",
            is_active=True,
        )
        tokens = create_admin_tokens(self.admin)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    @patch("chat.views.NotificationService.send_to_partner")
    def test_admin_send_triggers_partner_push(self, mock_send_to_partner):
        response = self.api.post(
            "/api/chat/send/",
            data={"receiver_id": self.partner.id, "content": "Hello there"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_send_to_partner.assert_called_once()
