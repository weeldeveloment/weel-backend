from rest_framework import serializers
from .models import ChatMessage
from django.contrib.auth import get_user_model
from users.models.partners import Partner

User = get_user_model()


class ActorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=['admin', 'partner'])
    full_name = serializers.CharField()
    email = serializers.CharField(allow_blank=True, required=False)
    username = serializers.CharField(allow_blank=True, required=False)
    phone_number = serializers.CharField(allow_blank=True, required=False)

    @staticmethod
    def from_admin(user: User):
        first_name = (getattr(user, 'first_name', '') or '').strip()
        last_name = (getattr(user, 'last_name', '') or '').strip()
        full_name = f"{first_name} {last_name}".strip() or getattr(user, 'email', '') or str(user)
        return {
            'id': user.id,
            'role': 'admin',
            'full_name': full_name,
            'email': getattr(user, 'email', '') or '',
            'username': getattr(user, 'username', '') or '',
            'phone_number': '',
        }

    @staticmethod
    def from_partner(partner: Partner):
        full_name = f"{(partner.first_name or '').strip()} {(partner.last_name or '').strip()}".strip() or partner.username
        return {
            'id': partner.id,
            'role': 'partner',
            'full_name': full_name,
            'email': partner.email or '',
            'username': partner.username or '',
            'phone_number': partner.phone_number or '',
        }


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.SerializerMethodField()
    receiver_id = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()
    receiver_type = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'conversation_id',
            'sender_id',
            'receiver_id',
            'sender_type',
            'receiver_type',
            'content',
            'is_read',
            'created_at',
            'updated_at',
        ]

    def get_sender_id(self, obj: ChatMessage):
        return obj.sender_id

    def get_receiver_id(self, obj: ChatMessage):
        return obj.receiver_id

    def get_sender_type(self, obj: ChatMessage):
        return obj.sender_type

    def get_receiver_type(self, obj: ChatMessage):
        return obj.receiver_type


class ConversationSerializer(serializers.Serializer):
    counterpart = ActorSerializer()
    conversation_id = serializers.IntegerField()
    last_message = ChatMessageSerializer(required=False, allow_null=True)
    unread_count = serializers.IntegerField()
