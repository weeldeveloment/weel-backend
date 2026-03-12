from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from users.tokens import TokenMetadata

User = get_user_model()


def create_admin_tokens(user):
    refresh = RefreshToken()
    access = AccessToken()

    common_claims = {
        TokenMetadata.TOKEN_SUBJECT: str(user.pk),
        TokenMetadata.TOKEN_ISSUER: getattr(settings, "JWT_ISSUER", "weel-backend"),
        TokenMetadata.TOKEN_USER_TYPE: "admin",
    }

    for key, value in common_claims.items():
        refresh[key] = value
        access[key] = value

    refresh[TokenMetadata.TOKEN_TYPE_CLAIM] = "refresh"
    access[TokenMetadata.TOKEN_TYPE_CLAIM] = "access"

    return {
        "refresh": str(refresh),
        "access": str(access),
    }


class AdminJWTAuthentication(JWTAuthentication):
    def authenticate(self, request: Request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            raise exceptions.AuthenticationFailed(
                _("Invalid authorization header"), code="bad_authorization_header"
            )

        validated_token = self.get_validated_token(raw_token)

        if validated_token.get(TokenMetadata.TOKEN_USER_TYPE) != "admin":
            return None

        user_id = validated_token.get(TokenMetadata.TOKEN_SUBJECT)
        if not user_id:
            raise exceptions.AuthenticationFailed(
                _("Invalid admin token"), code="invalid_admin_token"
            )

        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user:
            raise exceptions.AuthenticationFailed(
                _("Admin user not found"), code="admin_not_found"
            )

        return user, validated_token
