from django.conf import settings
from django.contrib.auth import get_user_model

from users.models.partners import Partner

from .models import Conversation

User = get_user_model()


class ChatRoutingError(Exception):
    pass


def get_default_admin():
    configured_admin_id = getattr(settings, "CHAT_DEFAULT_ADMIN_ID", None)
    if not configured_admin_id:
        raise ChatRoutingError("Chat default admin is not configured")

    admin_user = User.objects.filter(
        id=configured_admin_id,
        is_active=True,
        is_staff=True,
    ).first()
    if not admin_user:
        raise ChatRoutingError("Configured chat default admin is unavailable")

    return admin_user


def get_bootstrap_conversation_for_partner(partner: Partner):
    admin_user = get_default_admin()
    return {
        "counterpart": {
            "id": admin_user.id,
            "role": "admin",
            "full_name": (
                f"{(admin_user.first_name or '').strip()} {(admin_user.last_name or '').strip()}".strip()
                or admin_user.email
                or str(admin_user)
            ),
            "email": getattr(admin_user, "email", "") or "",
            "username": getattr(admin_user, "username", "") or "",
            "phone_number": "",
        },
        "conversation_id": 0,
        "last_message": None,
        "unread_count": 0,
    }


def get_or_create_conversation_for_message(sender_type: str, sender_id: int, receiver_id: int, receiver_type: str):
    if sender_type == "admin":
        if receiver_type != "partner":
            raise ChatRoutingError("Admins can only send messages to partners")

        admin_user = User.objects.filter(id=sender_id, is_active=True).first()
        partner = Partner.objects.filter(id=receiver_id, is_active=True).first()
        if not admin_user or not partner:
            raise ChatRoutingError("Partner not found")

        conversation, _ = Conversation.objects.get_or_create(admin_user=admin_user, partner=partner)
        return conversation, admin_user, partner

    if sender_type == "partner":
        if receiver_type != "admin":
            raise ChatRoutingError("Partners can only send messages to admins")

        partner = Partner.objects.filter(id=sender_id, is_active=True).first()
        admin_user = User.objects.filter(id=receiver_id, is_active=True, is_staff=True).first()
        if not partner:
            raise ChatRoutingError("Partner not found")
        if not admin_user:
            raise ChatRoutingError("Admin user not found")

        conversation, _ = Conversation.objects.get_or_create(admin_user=admin_user, partner=partner)
        return conversation, admin_user, partner

    raise ChatRoutingError("Unsupported chat actor")
