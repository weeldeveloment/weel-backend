from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response


from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


from .serializers import ClientDeviceSerializer, PartnerDeviceSerializer
from shared.permissions import IsClient, IsPartner
from users.services import ClientDeviceService, PartnerDeviceService
from users.authentication import ClientJWTAuthentication, PartnerJWTAuthentication


# Create your views here.


class FCMTokenUpdateView(APIView):
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClient]

    @swagger_auto_schema(
        tags=["Notification"],
        operation_summary="Update FCM token",
        operation_description="Update the client's Firebase Cloud Messaging(FCM) token\nfor push notification",
        request_body=ClientDeviceSerializer,
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="FCM token updated successfully",
                examples={
                    "application/json": {"detail": "FCM token updated successfully"}
                },
            ),
            status.HTTP_400_BAD_REQUEST: "Validation error",
            status.HTTP_401_UNAUTHORIZED: "Unauthorized",
        },
    )
    def post(self, request):
        serializer = ClientDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fcm_token = serializer.validated_data["fcm_token"]
        device_type = serializer.validated_data["device_type"]

        ClientDeviceService.register_device(
            client=request.user,
            fcm_token=fcm_token,
            device_type=device_type,
        )

        return Response(
            status=status.HTTP_200_OK,
            data={
                "detail": "FCM token updated successfully",
            },
        )


class PartnerFCMTokenUpdateView(APIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner]

    @swagger_auto_schema(
        tags=["Notification"],
        operation_summary="Update partner FCM token",
        operation_description="Update the partner's Firebase Cloud Messaging(FCM) token\nfor push notification",
        request_body=PartnerDeviceSerializer,
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Partner FCM token updated successfully",
                examples={
                    "application/json": {
                        "detail": "Partner FCM token updated successfully"
                    }
                },
            ),
            status.HTTP_400_BAD_REQUEST: "Validation error",
            status.HTTP_401_UNAUTHORIZED: "Unauthorized",
        },
    )
    def post(self, request):
        serializer = PartnerDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fcm_token = serializer.validated_data["fcm_token"]
        device_type = serializer.validated_data["device_type"]

        PartnerDeviceService.register_device(
            partner=request.user,
            fcm_token=fcm_token,
            device_type=device_type,
        )

        return Response(
            status=status.HTTP_200_OK,
            data={
                "detail": "Partner FCM token updated successfully",
            },
        )
