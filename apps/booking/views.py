from datetime import timedelta

from django.core.cache import cache
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, GenericAPIView, ListCreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend

from property.models import Property
from users.authentication import PartnerJWTAuthentication, ClientJWTAuthentication
from shared.permissions import IsClient, IsPartner, IsPartnerOwnerProperty
from admin_auth.authentication import AdminJWTAuthentication
from admin_auth.permissions import IsAdminUser
from .models import CalendarDate, Booking
from .serializers import (
    CalendarDateSerializer,
    PropertyCalendarDateRangeSerializer,
    ClientBookingCreateSerializer,
    ClientBookingListSerializer,
    PartnerBookingListSerializer,
    ClientBookingDetailSerializer,
    ClientBookingHistoryListSerializer,
    ClientBookingHistoryDetailSerializer,
    AdminBookingListSerializer,
)
from .filters import PropertyCalenderDateFilter
from .services import CalendarDateService, BookingService

property_id_param = openapi.Parameter(
    "property_id",
    openapi.IN_PATH,
    description="Unique property GUID",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_UUID,
)

booking_id_param = openapi.Parameter(
    "booking_id",
    openapi.IN_PATH,
    description="Unique booking GUID",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_UUID,
)

status_query_param = openapi.Parameter(
    "status",
    openapi.IN_QUERY,
    description="Filter bookings by status",
    type=openapi.TYPE_STRING,
    required=False,
)

# Create your views here.


class PropertyCalendarDateListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CalendarDateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = PropertyCalenderDateFilter

    def get_property(self):
        property_id = self.kwargs["property_id"]

        property = Property.objects.filter(
            guid=property_id,
            is_verified=True,
        ).first()

        if not property:
            raise NotFound(_("Property not found"))

        return property

    def list(self, request, *args, **kwargs):
        property = self.get_property()

        queryset = CalendarDate.objects.filter(property=property)
        filterset = self.filterset_class(
            data=request.query_params,
            queryset=queryset,
            request=request,
        )

        if not filterset.is_valid():
            raise ValidationError(filterset.errors)

        from_date = filterset.form.cleaned_data["from_date"]
        to_date = filterset.form.cleaned_data["to_date"]
        status_filer = filterset.form.cleaned_data.get("status")

        # for validation only(It won't work without it)
        filterset_qs = filterset.qs

        calendar_dates = queryset.filter(date__range=(from_date, to_date))
        status_by_date = dict(calendar_dates.values_list("date", "status"))

        calendar = []
        current_date = from_date

        while current_date <= to_date:
            if current_date in status_by_date:
                resolved_status = status_by_date[current_date]
            else:
                cache_key = f"calendar:hold:{property.guid}:{current_date.isoformat()}"
                if cache.get(cache_key):
                    resolved_status = CalendarDate.CalendarStatus.HELD
                else:
                    resolved_status = CalendarDate.CalendarStatus.AVAILABLE
            if not status_filer or resolved_status == status_filer:
                calendar.append(
                    {
                        "date": current_date,
                        "status": resolved_status,
                    }
                )

            current_date += timedelta(days=1)

        return Response(
            status=status.HTTP_200_OK,
            data={
                "property_id": property.guid,
                "range": {
                    "from_date": from_date,
                    "to_date": to_date,
                },
                "calendar": calendar,
            },
        )

    @swagger_auto_schema(
        tags=["Booking / Calendar"],
        operation_summary="Retrieve property calendar availability",
        operation_description="Returns the calendar for a property within the specified date range",
        manual_parameters=[property_id_param],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PropertyCalendarDateBlockView(GenericAPIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]
    serializer_class = PropertyCalendarDateRangeSerializer

    def get_property(self, property_id):
        property = (
            Property.objects.filter(guid=property_id, is_verified=True)
            .select_related("partner")
            .first()
        )
        if not property:
            raise NotFound(_("Property not found"))

        self.check_object_permissions(self.request, property)
        return property

    @swagger_auto_schema(
        tags=["Booking / Calendar"],
        operation_summary="Block dates in property calendar",
        operation_description="Blocks one or more dates in the property calendar",
        manual_parameters=[property_id_param],
    )
    def post(self, request, property_id):
        property = self.get_property(property_id)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from_date = serializer.validated_data["from_date"]
        to_date = serializer.validated_data["to_date"]
        is_single_day = serializer.validated_data["is_single_day"]

        calendar_dates = CalendarDateService(
            property=property,
            from_date=from_date,
            to_date=to_date,
        )
        days = calendar_dates.block()

        data = {
            "detail": _("You have successfully blocked the booking dates"),
            "property_id": property.guid,
        }

        if is_single_day:
            data["range"] = {"from_date": from_date.isoformat()}
            data["day"] = from_date.isoformat()
        else:
            data["range"] = {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            }
            data["days"] = [day.isoformat() for day in days]

        return Response(
            status=status.HTTP_200_OK,
            data=data,
        )


class PropertyCalendarDateUnblockView(GenericAPIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]
    serializer_class = PropertyCalendarDateRangeSerializer

    def get_property(self, property_id):
        property = (
            Property.objects.filter(guid=property_id, is_verified=True)
            .select_related("partner")
            .first()
        )
        if not property:
            raise NotFound(_("Property not found"))

        self.check_object_permissions(self.request, property)
        return property

    @swagger_auto_schema(
        tags=["Booking / Calendar"],
        operation_summary="Unblock dates in property calendar",
        operation_description="Removes blocked dates from the property calendar",
        manual_parameters=[property_id_param],
    )
    @transaction.atomic
    def post(self, request, property_id):
        property = self.get_property(property_id)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from_date = serializer.validated_data["from_date"]
        to_date = serializer.validated_data["to_date"]
        is_single_day = serializer.validated_data["is_single_day"]

        calendar_dates = CalendarDateService(
            property=property, from_date=from_date, to_date=to_date
        )
        days = calendar_dates.unblock()

        data = {
            "detail": _("You have successfully unblocked the booking dates"),
            "property_id": property.guid,
        }

        if is_single_day:
            data["range"] = {"from_date": from_date.isoformat()}
            data["day"] = from_date.isoformat()
        else:
            data["range"] = {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            }
            data["days"] = [day.isoformat() for day in days]

        return Response(
            status=status.HTTP_200_OK,
            data=data,
        )


class PropertyCalendarDateHoldView(GenericAPIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]
    serializer_class = PropertyCalendarDateRangeSerializer

    def get_property(self, property_id):
        property = (
            Property.objects.filter(guid=property_id, is_verified=True)
            .select_related("partner")
            .first()
        )
        if not property:
            raise NotFound(_("Property not found"))

        self.check_object_permissions(self.request, property)
        return property

    @swagger_auto_schema(
        tags=["Booking / Calendar"],
        operation_summary="Temporarily hold dates for 30 minutes",
        operation_description="Temporarily holds one or more dates for a client during the booking process. The client has 30 minutes to complete payment.",
        manual_parameters=[property_id_param],
    )
    def post(self, request, property_id):
        property = self.get_property(property_id)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from_date = serializer.validated_data["from_date"]
        to_date = serializer.validated_data["to_date"]
        is_single_day = serializer.validated_data["is_single_day"]

        calendar_dates = CalendarDateService(
            property=property,
            from_date=from_date,
            to_date=to_date,
        )
        days = calendar_dates.hold()

        data = {
            "detail": _("You have successfully held your booking dates for 30 minutes"),
            "property_id": property.guid,
        }

        if is_single_day:
            data["range"] = {"from_date": from_date.isoformat()}
            data["day"] = from_date.isoformat()
        else:
            data["range"] = {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            }
            data["days"] = [day.isoformat() for day in days]

        return Response(
            status=status.HTTP_200_OK,
            data=data,
        )


class PropertyCalendarDateUnholdView(GenericAPIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]
    serializer_class = PropertyCalendarDateRangeSerializer

    def get_property(self, property_id):
        property = (
            Property.objects.filter(guid=property_id, is_verified=True)
            .select_related("partner")
            .first()
        )
        if not property:
            raise NotFound(_("Property not found"))

        self.check_object_permissions(self.request, property)
        return property

    @swagger_auto_schema(
        tags=["Booking / Calendar"],
        operation_summary="Release held dates",
        operation_description="Releases previously held dates before the 30-minute hold expires",
        manual_parameters=[property_id_param],
    )
    def post(self, request, property_id):
        property = self.get_property(property_id)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from_date = serializer.validated_data["from_date"]
        to_date = serializer.validated_data["to_date"]
        is_single_day = serializer.validated_data["is_single_day"]

        calendar_dates = CalendarDateService(
            property=property, from_date=from_date, to_date=to_date
        )
        days = calendar_dates.unhold()

        data = {
            "detail": _("You have successfully unheld the booking dates"),
            "property_id": property.guid,
        }

        if is_single_day:
            data["range"] = {"from_date": from_date.isoformat()}
            data["day"] = from_date.isoformat()
        else:
            data["range"] = {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            }
            data["days"] = [day.isoformat() for day in days]

        return Response(
            status=status.HTTP_200_OK,
            data=data,
        )


class ClientBookingListCreateView(ListCreateAPIView):
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClient]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ClientBookingCreateSerializer
        return ClientBookingListSerializer

    def get_queryset(self):
        client = self.request.user
        status_param = self.request.query_params.get("status")

        booking = (
            Booking.objects.filter(client=client)
            .select_related("property")
            .prefetch_related("property__property_images")
        )
        if status_param:
            statuses = [s_p.strip() for s_p in status_param.split(",") if s_p.strip()]
            valid_statuses = set(Booking.BookingStatus)
            invalid_status = [s for s in statuses if s not in valid_statuses]
            if invalid_status:
                raise ValidationError(
                    {
                        "status": _(
                            "Invalid status: {invalid_status}, allowed are: {valid_statuses}"
                        ).format(
                            invalid_status=", ".join(invalid_status),
                            valid_statuses=", ".join(valid_statuses),
                        )
                    }
                )
            booking = booking.filter(status__in=statuses)
        return booking

    def get_property(self, property_id):
        property = (
            Property.objects.filter(guid=property_id, is_verified=True)
            .select_related("partner", "property_location")
            .first()
        )
        if not property:
            raise NotFound(_("Property not found"))
        return property

    def create(self, request, *args, **kwargs):
        property_id = request.data["property_id"]
        property = self.get_property(property_id)

        serializer = self.get_serializer(
            data=request.data,
            context={"property": property},
        )
        serializer.is_valid(raise_exception=True)

        booking_service = BookingService(client=request.user, property=property)
        booking, hold = booking_service.create_booking(
            check_in=serializer.validated_data["check_in"],
            check_out=serializer.validated_data["check_out"],
            data=serializer.validated_data,
        )
        return Response(
            status=status.HTTP_201_CREATED,
            data={
                "booking_id": booking.guid,
                "partner": {
                    "username": property.partner.username,
                    "first_name": property.partner.first_name,
                    "last_name": property.partner.first_name,
                    "phone_number": property.partner.phone_number,
                },
                "check_in": booking.check_in,
                "check_out": booking.check_out,
                "property_location": {
                    "latitude": property.property_location.latitude,
                    "longitude": property.property_location.longitude,
                },
                "status": booking.status,
            },
        )

    @swagger_auto_schema(
        tags=["Client / Booking"],
        operation_summary="List client bookings",
        operation_description="Return a list of booking related to the authenticated client",
        manual_parameters=[status_query_param],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=["Client / Booking"],
        operation_summary="Create booking and payment hold",
        operation_description="Creates a **PENDING booking** and places a **payment hold (UZS)**",
        request_body=ClientBookingCreateSerializer,
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ClientBookingDetailView(APIView):
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClient]

    def get_booking(self, booking_id, client):
        booking = (
            Booking.objects.filter(guid=booking_id, client=client)
            .select_related("property", "property__property_location")
            .first()
        )
        if not booking:
            raise NotFound(_("Booking not found"))

        return booking

    @swagger_auto_schema(
        tags=["Client / Booking"],
        operation_summary="Retrieve client booking details",
        operation_description="Retrieve information about a specific booking belonging to the authenticated client",
        manual_parameters=[booking_id_param],
    )
    def get(self, request, booking_id):
        booking = self.get_booking(booking_id, request.user)

        serializer = ClientBookingDetailSerializer(
            booking,
            context={"request": request},
        )
        return Response(
            status=status.HTTP_200_OK,
            data=serializer.data,
        )


class ClientBookingHistoryListView(ListAPIView):
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClient]
    serializer_class = ClientBookingHistoryListSerializer

    def get_queryset(self):
        client = self.request.user
        booking = (
            Booking.objects.filter(client=client)
            .select_related(
                "property",
                "property__property_type",
            )
            .prefetch_related("property__property_images")
        )
        return booking

    @swagger_auto_schema(
        tags=["Client / Booking"],
        operation_summary="Retrieve booking history",
        operation_description="Returns a list of history bookings created by the authenticated client",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ClientBookingHistoryDetailView(APIView):
    def get_booking(self, booking_id, client):
        booking = (
            Booking.objects.filter(
                guid=booking_id,
                client=client,
            )
            .select_related(
                "property",
                "booking_price",
                "property__property_location",
            )
            .first()
        )
        if not booking:
            raise NotFound(_("Booking not found"))
        return booking

    @swagger_auto_schema(
        tags=["Client / Booking"],
        operation_summary="Retrieve history booking details",
        operation_description="Returns detailed information about a specific booking history belonging to the authenticated client",
        manual_parameters=[booking_id_param],
    )
    def get(self, request, booking_id):
        booking = self.get_booking(booking_id, request.user)

        serializer = ClientBookingHistoryDetailSerializer(
            booking,
            context={"request": request},
        )
        return Response(status=status.HTTP_200_OK, data=serializer.data)


class ClientBookingCancelView(APIView):
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClient]

    def get_booking(self, booking_id, client):
        booking = (
            Booking.objects.filter(guid=booking_id, client=client)
            .select_related("client", "property")
            .first()
        )
        if not booking:
            raise NotFound(_("Booking not found"))

        return booking

    @swagger_auto_schema(
        tags=["Client / Booking"],
        operation_summary="Cancel booking",
        operation_description="Allows a client to cancel their booking",
        manual_parameters=[booking_id_param],
    )
    def post(self, request, booking_id):
        booking = self.get_booking(booking_id, request.user)

        booking_service = BookingService(
            client=request.user,
            property=booking.property,
        )
        booking = booking_service.cancel_booking(booking)
        return Response(
            status=status.HTTP_200_OK,
            data={
                "booking_id": booking.guid,
                "status": booking.status,
                "cancellation_reason": booking.cancellation_reason,
            },
        )


class PartnerBookingAcceptView(APIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]

    def get_booking(self, booking_id):
        booking = (
            Booking.objects.filter(guid=booking_id).select_related("property").first()
        )
        if not booking:
            raise ValidationError(_("Booking not found"))

        self.check_object_permissions(self.request, booking.property)
        return booking

    @swagger_auto_schema(
        tags=["Partner / Booking"],
        operation_summary="Accept booking",
        operation_description="Allows a partner to accept a booking request",
        manual_parameters=[booking_id_param],
    )
    def post(self, request, booking_id):
        booking = self.get_booking(booking_id)

        booking_service = BookingService(
            client=booking.client,
            property=booking.property,
        )
        booking = booking_service.partner_accept(booking, notify_partner=False)
        return Response(
            status=status.HTTP_200_OK,
            data={
                "booking_id": booking.guid,
                "status": booking.status,
            },
        )


class PartnerBookingCancelView(APIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]

    def get_booking(self, booking_id):
        booking = (
            Booking.objects.filter(guid=booking_id).select_related("property").first()
        )
        if not booking:
            raise ValidationError(_("Booking not found"))

        self.check_object_permissions(self.request, booking.property)
        return booking

    @swagger_auto_schema(
        tags=["Partner / Booking"],
        operation_summary="Cancel booking",
        operation_description="A cancellation reason may be provided and the booking status",
        manual_parameters=[booking_id_param],
    )
    def post(self, request, booking_id):
        booking = self.get_booking(booking_id)

        booking_service = BookingService(
            client=booking.client,
            property=booking.property,
        )
        booking = booking_service.partner_cancel(booking, notify_partner=False)
        return Response(
            status=status.HTTP_200_OK,
            data={
                "booking_id": booking.guid,
                "status": booking.status,
            },
        )


class PartnerBookingListView(ListAPIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner]
    serializer_class = PartnerBookingListSerializer

    def get_queryset(self):
        partner = self.request.user
        status_param = self.request.query_params.get("status")

        booking = Booking.objects.filter(property__partner=partner).select_related(
            "property",
            "client",
        )

        if status_param:
            statuses = [s_p.strip() for s_p in status_param.split(",") if s_p.strip()]

            valid_statuses = set(Booking.BookingStatus)
            invalid_status = [s for s in statuses if s not in valid_statuses]
            if invalid_status:
                raise ValidationError(
                    {
                        "status": _(
                            "Invalid status: {invalid_status}, allowed are: {valid_statuses}"
                        ).format(
                            invalid_status=", ".join(invalid_status),
                            valid_statuses=", ".join(valid_statuses),
                        )
                    }
                )
            booking = booking.filter(status__in=statuses)
        return booking

    @swagger_auto_schema(
        tags=["Partner / Booking"],
        operation_summary="List partner bookings",
        operation_description="Return a list of booking related to the authenticated partner",
        manual_parameters=[status_query_param],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PartnerCompleteBookingView(APIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]

    def get_booking(self, booking_id):
        booking = (
            Booking.objects.filter(guid=booking_id).select_related("property").first()
        )
        if not booking:
            raise NotFound(_("Booking not found"))

        self.check_object_permissions(self.request, booking.property)
        return booking

    @swagger_auto_schema(
        tags=["Partner / Booking"],
        operation_summary="Complete booking",
        operation_description="Marks as confirmed booking as completed when the user arrives\nCharges 50% of the hold booking price",
        manual_parameters=[booking_id_param],
    )
    def post(self, request, booking_id):
        booking = self.get_booking(booking_id)

        booking_service = BookingService(
            client=booking.client, property=booking.property
        )
        booking = booking_service.complete_booking(booking, notify_partner=False)
        booking.refresh_from_db()
        return Response(
            status=status.HTTP_200_OK,
            data={
                "booking_id": str(booking.guid),
                "subtotal": str(booking.booking_price.subtotal),
                "hold_amount": str(booking.booking_price.hold_amount),
                "charge_amount": str(booking.booking_price.charge_amount),
                "status": booking.status,
            },
        )


class PartnerNoShowBookingView(APIView):
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner, IsPartnerOwnerProperty]

    def get_booking(self, booking_id):
        booking = (
            Booking.objects.filter(guid=booking_id).select_related("property").first()
        )
        if not booking:
            raise NotFound(_("Booking not found"))

        self.check_object_permissions(self.request, booking.property)
        return booking

    @swagger_auto_schema(
        tags=["Partner / Booking"],
        operation_summary="Mark booking as no-show",
        operation_description="Marks a confirmed booking as no-show when the user does not arrive",
        manual_parameters=[booking_id_param],
    )
    def post(self, request, booking_id):
        booking = self.get_booking(booking_id)

        booking_service = BookingService(
            client=booking.client, property=booking.property
        )
        booking = booking_service.mark_no_show(booking, notify_partner=False)
        return Response(
            {
                "booking_id": booking.guid,
                "status": booking.status,
                "cancellation_reason": booking.cancellation_reason,
                "cancelled_at": booking.cancelled_at,
            },
            status=status.HTTP_200_OK,
        )


class AdminBookingPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminBookingListView(ListAPIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminUser]
    serializer_class = AdminBookingListSerializer
    pagination_class = AdminBookingPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["booking_number", "client__phone_number"]
    ordering_fields = ["created_at", "check_in", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Booking.objects.select_related(
                "client",
                "property",
                "property__property_type",
                "booking_price",
            )
            .order_by("-created_at")
        )

    @swagger_auto_schema(
        tags=["Admin / Booking"],
        operation_summary="List all bookings for admin",
        operation_description="Returns a paginated list of all bookings with filtering, search, and ordering support",
        manual_parameters=[
            status_query_param,
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Search by booking number or client phone number",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "ordering",
                openapi.IN_QUERY,
                description="Order by field (created_at, check_in, status). Prefix with '-' for descending",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
