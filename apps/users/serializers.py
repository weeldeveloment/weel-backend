from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models.clients import Client, ClientDevice


class OTPCodeFieldAliasMixin:
    """Accept both otp_code and otp-code in request body."""

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = dict(data)
            if "otp-code" in data and "otp_code" not in data:
                data["otp_code"] = data.pop("otp-code")
        return super().to_internal_value(data)
from .models.partners import Partner, PartnerDevice, PartnerDocument, DocumentType
from .models.logs import SmsPurpose
from .services import OTPRedisService, PasswordService

from shared.utility import PASSWORD_REGEX


class UserPhoneNumberSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value: str):
        if not value.startswith("998"):
            raise serializers.ValidationError(_("Phone number must start with 998"))
        return value


class ClientOTPLoginVerifySerializer(OTPCodeFieldAliasMixin, serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    fcm_token = serializers.CharField(required=False, allow_null=True)
    device_type = serializers.ChoiceField(
        required=False,
        choices=ClientDevice.ClientDeviceType,
    )
    otp_code = serializers.CharField(
        min_length=OTPRedisService.OTP_LENGTH,
        max_length=OTPRedisService.OTP_LENGTH,
        required=True,
    )

    def validate(self, attrs):
        phone_number = attrs["phone_number"]
        otp_code = attrs["otp_code"]

        is_valid, message = OTPRedisService.verify_otp(
            phone_number, otp_code, SmsPurpose.LOGIN
        )

        if not is_valid:
            raise serializers.ValidationError(message)

        try:
            client = Client.objects.get(phone_number=phone_number, is_active=True)
        except Client.DoesNotExist:
            alt_phone = (
                phone_number[1:] if phone_number.startswith("+") else f"+{phone_number}"
            )
            try:
                client = Client.objects.get(phone_number=alt_phone, is_active=True)
            except Client.DoesNotExist:
                raise serializers.ValidationError(_("Client not found"))

        attrs["client"] = client
        return attrs


class ClientRegisterSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False, min_length=2, max_length=64)
    last_name = serializers.CharField(required=False, min_length=2, max_length=64)

    def validate_phone_number(self, value):
        if Client.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                _("Client with this phone number already exists")
            )
        return value


class ClientOTPRegistrationVerifySerializer(OTPCodeFieldAliasMixin, serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    fcm_token = serializers.CharField(required=False, allow_null=True)
    device_type = serializers.ChoiceField(
        required=False,
        choices=ClientDevice.ClientDeviceType,
    )
    otp_code = serializers.CharField(
        min_length=OTPRedisService.OTP_LENGTH,
        max_length=OTPRedisService.OTP_LENGTH,
        required=True,
    )

    def validate(self, attrs):
        phone_number = attrs["phone_number"]
        otp_code = attrs["otp_code"]

        registration_data = OTPRedisService.get_registration_data(
            phone_number, SmsPurpose.REGISTER
        )
        if not registration_data:
            raise serializers.ValidationError(
                _("Registration data not found. Please start registration again")
            )

        is_valid, message = OTPRedisService.verify_otp(
            phone_number, otp_code, SmsPurpose.REGISTER
        )

        if not is_valid:
            raise serializers.ValidationError(message)

        attrs["registration_data"] = registration_data

        if Client.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError(_("Client already registered"))

        attrs["phone_number"] = phone_number

        return attrs


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)


class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = (
            "id",
            "phone_number",
            "first_name",
            "last_name",
            "avatar",
        )
        read_only_fields = ("id", "phone_number")


# class PartnerPasswordLoginSerializer(serializers.Serializer):
#     phone_number = serializers.CharField(required=True)
#     password = serializers.CharField(required=True)
#
#     def validate(self, attrs):
#         phone_number = attrs["phone_number"]
#         password = attrs["password"]
#
#         try:
#             partner = Partner.objects.get(phone_number=phone_number, is_active=True)
#         except Partner.DoesNotExist:
#             raise serializers.ValidationError(_("Invalid credentials"))
#
#         if not PasswordService.verify_password(password, partner.password):
#             raise serializers.ValidationError(_("Invalid credentials"))
#
#         attrs["partner"] = partner
#         return attrs


class PartnerOTPLoginSerializer(OTPCodeFieldAliasMixin, serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    fcm_token = serializers.CharField(required=False, allow_null=True)
    device_type = serializers.ChoiceField(
        required=False,
        choices=PartnerDevice.PartnerDeviceType,
    )
    otp_code = serializers.CharField(
        min_length=OTPRedisService.OTP_LENGTH,
        max_length=OTPRedisService.OTP_LENGTH,
        required=True,
    )

    def validate(self, attrs):
        phone_number = attrs["phone_number"]
        otp_code = attrs["otp_code"]

        is_valid, message = OTPRedisService.verify_otp(
            phone_number, otp_code, SmsPurpose.PARTNER_LOGIN
        )

        if not is_valid:
            raise serializers.ValidationError(message)

        try:
            partner = Partner.objects.get(phone_number=phone_number, is_active=True)
        except Partner.DoesNotExist:
            alt_phone = (
                phone_number[1:]
                if phone_number.startswith("+")
                else f"+{phone_number}"
            )
            try:
                partner = Partner.objects.get(
                    phone_number=alt_phone, is_active=True
                )
            except Partner.DoesNotExist:
                if OTPRedisService.is_test_phone_for_purpose(
                    phone_number, SmsPurpose.PARTNER_LOGIN
                ):
                    canonical = (
                        phone_number
                        if phone_number.startswith("+")
                        else f"+{phone_number}"
                    )
                    phone_clean = canonical.replace("+", "").strip()
                    if not phone_clean.startswith("998"):
                        phone_clean = "998" + phone_clean
                    canonical = "+" + phone_clean
                    partner, created = Partner.objects.get_or_create(
                        phone_number=canonical,
                        defaults={
                            "first_name": "Test",
                            "last_name": "Partner",
                            "username": f"test_partner_{phone_clean}",
                            "is_active": True,
                        },
                    )
                else:
                    raise serializers.ValidationError(_("Partner not found"))

        attrs["partner"] = partner
        return attrs


class PartnerOTPRegisterSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    username = serializers.CharField(required=True, min_length=2)
    first_name = serializers.CharField(required=True, min_length=2, max_length=64)
    last_name = serializers.CharField(required=True, min_length=2, max_length=64)
    email = serializers.EmailField(required=False, write_only=True)
    # password = serializers.RegexField(
    #     regex=PASSWORD_REGEX,
    #     required=True,
    #     write_only=True,
    #     help_text=_(
    #         "Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character"
    #     ),
    # )

    def validate_phone_number(self, value):
        if Partner.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                _("Partner with this phone number already exists")
            )
        return value

    def validate_username(self, value):
        if Partner.objects.filter(username=value).exists():
            raise serializers.ValidationError(_("Username already exists"))
        return value

    def validate_email(self, value):
        if value and Partner.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("Partner with this email already exists")
            )
        return value

    # def validate_password(self, value):
    #     if value and not PasswordService.validate_password_strength(value):
    #         raise serializers.ValidationError(
    #             _("Password must be at least 8 characters long")
    #         )
    #     return value


class PartnerOTPRegisterVerifySerializer(OTPCodeFieldAliasMixin, serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    fcm_token = serializers.CharField(required=False, allow_null=True)
    device_type = serializers.ChoiceField(
        required=False,
        choices=PartnerDevice.PartnerDeviceType,
    )
    otp_code = serializers.CharField(
        min_length=OTPRedisService.OTP_LENGTH,
        max_length=OTPRedisService.OTP_LENGTH,
        required=True,
    )

    def validate(self, attrs):
        phone_number = attrs["phone_number"]
        registration_data = OTPRedisService.get_registration_data(
            phone_number, SmsPurpose.PARTNER_REGISTER
        )
        if not registration_data:
            raise serializers.ValidationError(
                _("Registration data not found. Please start registration again")
            )
        otp_code = attrs["otp_code"]

        is_valid, message = OTPRedisService.verify_otp(
            phone_number, otp_code, SmsPurpose.PARTNER_REGISTER
        )

        if not is_valid:
            raise serializers.ValidationError(message)

        attrs["registration_data"] = registration_data

        if Partner.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError(_("Partner already registered"))

        attrs["phone_number"] = phone_number

        return attrs


class ResendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)

    def validate_phone_number(self, value: str):
        if not value.startswith("998"):
            raise serializers.ValidationError(_("Phone number must start with 998"))
        return value


class PartnerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ["id", "username", "first_name", "last_name", "phone_number", "avatar"]
        read_only_fields = ("id",)


class PartnerPassportUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerDocument
        fields = ("document",)

    def validate_document(self, file):
        max_size = 5 * 1024 * 1024  # 5MB
        if file.size > max_size:
            raise serializers.ValidationError("File size must be ≤ 5MB")
        return file

    def create(self, validated_data):
        partner = self.context["partner"]

        # один паспорт на партнёра
        # PartnerDocument.objects.filter(
        #     partner=partner,
        #     type=DocumentType.PASSPORT,
        # ).delete()

        return PartnerDocument.objects.create(
            partner=partner,
            type=DocumentType.PASSPORT,
            document=validated_data["document"],
        )


# class PartnerChangePasswordSerializer(serializers.Serializer):
#     current_password = serializers.RegexField(
#         regex=PASSWORD_REGEX,
#         required=True,
#         write_only=True,
#         help_text=_(
#             "Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character"
#         ),
#     )
#     new_password = serializers.RegexField(
#         regex=PASSWORD_REGEX,
#         required=True,
#         write_only=True,
#         help_text=_(
#             "Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character"
#         ),
#     )
#
#     def validate_new_password(self, value):
#         if not PasswordService.validate_password_strength(value):
#             raise serializers.ValidationError(
#                 _("Password must be at least 8 characters long")
#             )
#         return value
