from unittest.mock import patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory
from rest_framework import status

from admin_auth.authentication import create_admin_tokens
from users.models.partners import Partner
from users.tokens import create_partner_tokens


User = get_user_model()


@override_settings(CHAT_DEFAULT_ADMIN_ID=1)
class ChatPushNotificationTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin = User.objects.create(username="admin", is_staff=True, is_active=True)
        self.partner = Partner.objects.create(
            first_name="Test",
            last_name="Partner",
            username="partner1",
            phone_number="+998901234568",
            is_active=True,
        )
        tokens = create_admin_tokens(self.admin)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    @patch("chat.views.NotificationService.send_to_partner")
    def test_admin_send_triggers_partner_push(self, mock_send_to_partner):
        response = self.api.post(
            "/api/chat/send/",
            data={"receiver_id": self.partner.id, "receiver_type": "partner", "content": "Hello there"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_send_to_partner.assert_called_once()


@override_settings(CHAT_DEFAULT_ADMIN_ID=1)
class PartnerChatFlowTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.factory = APIRequestFactory()
        self.admin = User.objects.create(username="admin", is_staff=True, is_active=True)
        self.partner = Partner.objects.create(
            first_name="Test",
            last_name="Partner",
            username="partner1",
            phone_number="+998901234568",
            is_active=True,
        )
        tokens = create_partner_tokens(self.partner, self.factory.get("/"))
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def test_partner_gets_default_admin_conversation_when_empty(self):
        response = self.api.get("/api/chat/conversations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["counterpart"]["id"], self.admin.id)
        self.assertEqual(response.data[0]["counterpart"]["role"], "admin")
        self.assertEqual(response.data[0]["unread_count"], 0)
        self.assertIsNone(response.data[0]["last_message"])

    def test_partner_send_requires_valid_admin(self):
        response = self.api.post(
            "/api/chat/send/",
            data={"receiver_id": 999999, "receiver_type": "admin", "content": "Hello there"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(CHAT_DEFAULT_ADMIN_ID=None)
    def test_partner_bootstrap_requires_configured_default_admin(self):
        response = self.api.get("/api/chat/conversations/")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
