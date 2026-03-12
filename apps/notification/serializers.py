from rest_framework import serializers

from users.models.clients import ClientDevice
from users.models.partners import PartnerDevice
from .models import PartnerNotification


class ClientDeviceSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(max_length=255)
    device_type = serializers.ChoiceField(choices=ClientDevice.ClientDeviceType)


class PartnerDeviceSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(max_length=255)
    device_type = serializers.ChoiceField(choices=PartnerDevice.PartnerDeviceType)


class PartnerNotificationSerializer(serializers.ModelSerializer):
    """Serializer for partner notifications"""
    
    class Meta:
        model = PartnerNotification
        fields = [
            "guid",
            "title",
            "body",
            "notification_type",
            "data",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields


class PartnerNotificationListSerializer(serializers.Serializer):
    """Serializer for notification list response"""
    notifications = PartnerNotificationSerializer(many=True)
    total = serializers.IntegerField()
    unread_count = serializers.IntegerField()


class MarkAsReadSerializer(serializers.Serializer):
    """Serializer for marking notifications as read"""
    notification_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
