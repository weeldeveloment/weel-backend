import uuid

from django.utils import timezone
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_framework import mixins, viewsets, status
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.generics import ListAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Story, StoryView
from .serializers import StoryCreateSerializer, StorySerializer, StoryDetailSerializer
from property.models import PropertyType
from shared.permissions import IsPartner, IsClient
from users.authentication import PartnerJWTAuthentication, ClientJWTAuthentication
from users.models import Client
from users.models import Partner


class StoryViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Story.objects.all()
    authentication_classes = [PartnerJWTAuthentication, ClientJWTAuthentication]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = "guid"
    lookup_url_kwarg = "story_id"

    def get_serializer_class(self):
        if self.action == "create":
            return StoryCreateSerializer
        if self.action == "retrieve":
            return StoryDetailSerializer
        return StorySerializer

    def get_permissions(self):
        if self.action in ["create", "destroy"]:
            return [IsPartner()]
        return [AllowAny()]

    def get_queryset(self):
        """Return only non-expired stories, newest first. Optional filter by property_type (guid)."""
        base = Story.objects.filter(
            expires_at__gt=timezone.now(),
            property__is_archived=False,
        ).order_by("-uploaded_at")

        if isinstance(self.request.user, Partner):
            return base.filter(property__partner=self.request.user)
        base = base.filter(is_verified=True)
        return _apply_property_type_filter(self.request, base)

    @swagger_auto_schema(
        tags=["Stories"],
        operation_summary="Retrieve all stories(non-expired)",
        operation_description="For clients property_type=<uuid> is required; request without it returns 404.",
        manual_parameters=[
            openapi.Parameter(
                "property_type",
                openapi.IN_QUERY,
                description="Property type GUID — required for client",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=False,
            ),
        ],
        responses={
            status.HTTP_200_OK: StorySerializer(many=True),
            status.HTTP_404_NOT_FOUND: "property_type is required for client",
        },
    )
    def list(self, request, *args, **kwargs):
        if not isinstance(request.user, Partner) and not request.query_params.get("property_type"):
            raise NotFound(_("Parametrlar kerak. property_type=<uuid> yuboring."))
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=["Story Media"],
        operation_summary="Retrieve a story(non-expired) media",
        operation_description="Retrieve a specific media from a story and count view for authenticated client",
        manual_parameters=[
            openapi.Parameter(
                "story_id",
                openapi.IN_PATH,
                description="Unique story GUID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
            ),
            openapi.Parameter(
                "media_id",
                openapi.IN_PATH,
                description="Unique media GUID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
            ),
        ],
        responses={
            status.HTTP_200_OK: StoryDetailSerializer,
            status.HTTP_404_NOT_FOUND: "Story not found",
        },
    )
    def retrieve_media(self, request, story_id=None, media_id=None):
        story_qs = Story.objects.filter(
            guid=story_id,
            expires_at__gt=timezone.now(),
        )
        
        # Check permissions/visibility
        if isinstance(request.user, Partner):
             # Try to find story owned by partner OR verified
             # Actually, if I just want to view a media, and I am the owner, I should see it.
             pass # Logic handled below by checking retrieved story
        else:
             story_qs = story_qs.filter(is_verified=True)

        story = story_qs.order_by("-uploaded_at").first()

        if not story:
            raise NotFound("Story not found")

        # Extra security check if it was found but not verified and user is partner
        if not story.is_verified:
             if not isinstance(request.user, Partner) or story.property.partner != request.user:
                 raise NotFound("Story not found")

        media = story.media.filter(guid=media_id).first()
        if not media:
            raise NotFound("Media not found")

        if isinstance(request.user, Client):
            story_view = StoryView.objects.get_or_create(
                story=story, client=request.user
            )[1]

            if story_view:
                cache_key = f"story:{story.guid}:views"

                if cache.get(cache_key) is None:
                    cache.set(cache_key, 0)

                cache.incr(cache_key)

        serializer = StoryDetailSerializer(
            story,
            context={
                "request": request,
                "media_id": media_id,
            },
        )
        return Response(status=status.HTTP_200_OK, data=serializer.data)

    @swagger_auto_schema(
        tags=["Stories"],
        operation_summary="Create a new story",
        operation_description="Create a new story, only partners can upload stories",
        request_body=StoryCreateSerializer,
        responses={
            status.HTTP_201_CREATED: StorySerializer,
            status.HTTP_400_BAD_REQUEST: "Bad request",
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=["Stories"],
        operation_summary="Delete all the stories entirely",
        operation_description="Delete all stories, only partners can delete their own stories",
        manual_parameters=[
            openapi.Parameter(
                "story_id",
                openapi.IN_PATH,
                description="Unique story GUID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
            )
        ],
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_404_NOT_FOUND: "Story not found",
        },
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        partner = self.request.user

        if instance.property.partner != partner:
            raise PermissionDenied(_("You don't have permission to delete this story"))
        return instance.delete()

    @swagger_auto_schema(
        tags=["Story Media"],
        operation_summary="Delete story media",
        operation_description="Delete a specific media from a story, only partners can delete their own stories",
        manual_parameters=[
            openapi.Parameter(
                "story_id",
                openapi.IN_PATH,
                description="Unique story GUID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            ),
            openapi.Parameter(
                "media_id",
                openapi.IN_PATH,
                description="Unique media GUID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            ),
        ],
    )
    def destroy_media(self, request, story_id=None, media_id=None):
        story = (
            Story.objects.filter(
                guid=story_id,
                expires_at__gt=timezone.now(),
            )
            .order_by("-uploaded_at")
            .first()
        )

        if not story:
            raise NotFound("Story not found")

        # Allow owner to delete even if unverified (and verification check removed from filter above)
        
        partner = request.user
        if partner != story.property.partner:
            # If not owner, maybe 404 if unverified? or 403?
            # Original logic was 404 if unverified.
            if not story.is_verified:
                 raise NotFound("Story not found")
            
            raise PermissionDenied(
                _("You don't have permission to delete this story media")
            )

        media = story.media.filter(guid=media_id).first()
        if not media:
            raise NotFound("Media not found")

        media.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PartnerStoryListView(ListAPIView):
    serializer_class = StorySerializer
    authentication_classes = [PartnerJWTAuthentication]
    permission_classes = [IsPartner]

    def get_queryset(self):
        return (
            Story.objects.filter(
                property__partner=self.request.user,
                expires_at__gt=timezone.now(),
            )
            .order_by("-uploaded_at")
            .select_related("property")
            .prefetch_related("media", "property__property_images")
        )

    @swagger_auto_schema(
        tags=["Stories"],
        operation_summary="Partner's own stories",
        operation_description="Retrieve all stories created by the authenticated partner (including unverified)",
        responses={status.HTTP_200_OK: StorySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


def _apply_property_type_filter(request, queryset):
    """Filter by property_type guid (?property_type=<uuid>). Invalid or non-existent guid = no filter, return all."""
    raw = request and request.query_params.get("property_type")
    if not raw:
        return queryset
    try:
        guid = uuid.UUID(str(raw).strip())
    except (ValueError, TypeError):
        return queryset
    if not PropertyType.objects.filter(guid=guid).exists():
        return queryset
    return queryset.filter(property__property_type__guid=guid)


class PublicStoryListView(ListAPIView):
    serializer_class = StorySerializer
    permission_classes = [AllowAny]
    authentication_classes = [ClientJWTAuthentication]

    def get_queryset(self):
        base_qs = (
            Story.objects.filter(
                is_verified=True,
                expires_at__gt=timezone.now(),
                property__is_archived=False,
            )
            .order_by("-uploaded_at")
            .select_related("property", "property__property_type")
            .prefetch_related("media", "property__property_images")
        )
        return _apply_property_type_filter(self.request, base_qs)

    @swagger_auto_schema(
        tags=["Stories"],
        operation_summary="Public stories list",
        operation_description="Request without parameters returns 404. property_type=<uuid> must be sent.",
        manual_parameters=[
            openapi.Parameter(
                "property_type",
                openapi.IN_QUERY,
                description="Property type GUID — required (e.g. dacha, sanatorium)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            ),
        ],
        responses={
            status.HTTP_200_OK: StorySerializer(many=True),
            status.HTTP_404_NOT_FOUND: "Parameters not provided",
        },
    )
    def get(self, request, *args, **kwargs):
        if not request.query_params.get("property_type"):
            raise NotFound(_("Parametrlar kerak. property_type=<uuid> yuboring."))
        return super().get(request, *args, **kwargs)

