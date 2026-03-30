import uuid
from typing import Final

from django.conf import settings

from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .models.clients import Client, ClientSession
from .models.partners import Partner, PartnerSession


class CustomRefreshToken(RefreshToken):
    def blacklist(self):
        try:
            user_type = self.get("user_type")
            if user_type == "client":
                user = Client.objects.get(guid=self["sub"])
            elif user_type == "partner":
                user = Partner.objects.get(guid=self["sub"])
            else:
                return

            super().blacklist()
        except Exception:
            pass


class TokenMetadata:
    TOKEN_TYPE_CLAIM: Final[str] = "type"
    TOKEN_SUBJECT: Final[str] = "sub"
    TOKEN_ISSUER: Final[str] = "iss"
    TOKEN_EXPIRE_TIME_CLAIM: Final[str] = "exp"
    TOKEN_CREATED_TIME_CLAIM: Final[str] = "iat"
    TOKEN_USER_TYPE: Final[str] = "user_type"


def get_user_ip(request: Request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def create_client_session(client: Client, request: Request):
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    device_id = request.META.get("HTTP_X_DEVICE_ID")
    last_ip = get_user_ip(request)

    session = ClientSession.objects.create(
        client=client, device_id=device_id, user_agent=user_agent, last_ip=last_ip
    )
    return session



def create_client_tokens(client: Client, request: Request):
    refresh = CustomRefreshToken()
    access = AccessToken()

    common_claims = {
        TokenMetadata.TOKEN_SUBJECT: str(client.guid),
        TokenMetadata.TOKEN_ISSUER: getattr(settings, "JWT_ISSUER"),
        TokenMetadata.TOKEN_USER_TYPE: "client",
    }

    for key, value in common_claims.items():
        refresh[key] = value
        access[key] = value

    refresh[TokenMetadata.TOKEN_TYPE_CLAIM] = "refresh"
    access[TokenMetadata.TOKEN_TYPE_CLAIM] = "access"

    session = create_client_session(client, request)

    return {
        "refresh": str(refresh),
        "access": str(access),
    }


def create_partner_session(partner: Partner, request: Request):
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    device_id = request.META.get("HTTP_X_DEVICE_ID")
    last_ip = get_user_ip(request)

    session = PartnerSession.objects.create(
        partner=partner, device_id=device_id, user_agent=user_agent, last_ip=last_ip
    )
    return session


def create_partner_tokens(partner: Partner, request: Request):
    refresh = CustomRefreshToken()
    access = AccessToken()

    common_claims = {
        TokenMetadata.TOKEN_SUBJECT: str(partner.guid),
        TokenMetadata.TOKEN_ISSUER: getattr(settings, "JWT_ISSUER"),
        TokenMetadata.TOKEN_USER_TYPE: "partner",
    }

    for key, value in common_claims.items():
        refresh[key] = value
        access[key] = value

    refresh[TokenMetadata.TOKEN_TYPE_CLAIM] = "refresh"
    access[TokenMetadata.TOKEN_TYPE_CLAIM] = "access"

    session = create_partner_session(partner, request)

    return {
        "refresh": str(refresh),
        "access": str(access),
    }


def rotate_tokens(refresh_token: str) -> dict:
    try:
        token = CustomRefreshToken(token=refresh_token)

        new_refresh = CustomRefreshToken()
        new_access = AccessToken()

        claims_to_copy = [
            TokenMetadata.TOKEN_SUBJECT,
            TokenMetadata.TOKEN_ISSUER,
            TokenMetadata.TOKEN_USER_TYPE,
        ]

        for claim in claims_to_copy:
            if claim in token:
                new_refresh[claim] = token[claim]
                new_access[claim] = token[claim]

        new_refresh[TokenMetadata.TOKEN_TYPE_CLAIM] = "refresh"
        new_access[TokenMetadata.TOKEN_TYPE_CLAIM] = "access"

        token.blacklist()
        return {"refresh": str(new_refresh), "access": str(new_access)}
    except Exception as e:
        raise ValueError("Invalid or expired refresh token")


def decode_token(token: str):
    try:
        untyped_token = UntypedToken(token)

        payload = untyped_token.payload

        required_claims = [
            TokenMetadata.TOKEN_SUBJECT,
            TokenMetadata.TOKEN_EXPIRE_TIME_CLAIM,
            TokenMetadata.TOKEN_USER_TYPE,
            TokenMetadata.TOKEN_TYPE_CLAIM,
        ]

        for claim in required_claims:
            if claim not in payload:
                raise InvalidToken(f"Missing required claim: {claim}")

        return payload

    except TokenError as e:
        raise InvalidToken(str(e))
