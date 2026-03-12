from rest_framework import serializers

from users.models.clients import ClientDevice
from users.models.partners import PartnerDevice


class ClientDeviceSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(max_length=255)
    device_type = serializers.ChoiceField(choices=ClientDevice.ClientDeviceType)


class PartnerDeviceSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(max_length=255)
    device_type = serializers.ChoiceField(choices=PartnerDevice.PartnerDeviceType)
