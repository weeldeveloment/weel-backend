from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from core import settings
from .models import Story, StoryMedia
from property.models import Property


class StoryMediaSerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField("get_media_url")

    class Meta:
        model = StoryMedia
        fields = ["guid", "media_type", "media_url"]

    def get_media_url(self, obj):
        request = self.context["request"]
        if not request:
            return obj.media.url

        return request.build_absolute_uri(obj.media.url)


class StorySerializer(serializers.ModelSerializer):
    property_id = serializers.CharField(source="property.guid", read_only=True)
    property_title = serializers.CharField(source="property.title", read_only=True)
    property_type_guid = serializers.SerializerMethodField("get_property_type_guid")
    property_image_url = serializers.SerializerMethodField("get_property_image_url")
    media = StoryMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Story
        fields = [
            "guid",
            "property_id",
            "property_title",
            "property_type_guid",
            "property_image_url",
            "media",
        ]

    def get_property_type_guid(self, obj):
        if not obj.property_id:
            return None
        pt = getattr(obj.property, "property_type", None)
        return str(pt.guid) if pt else None

    def get_property_image_url(self, obj):
        request = self.context["request"]
        first_image = (
            obj.property.property_images.filter(is_pending=False).order_by("order").first()
        )

        if first_image and request:
            return request.build_absolute_uri(first_image.image.url)
        return None


class StoryPropertySerializer(serializers.Serializer):
    guid = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)


class StoryDetailSerializer(serializers.ModelSerializer):
    property = StoryPropertySerializer()
    media = serializers.SerializerMethodField("get_media")
    views = serializers.SerializerMethodField("get_views")

    class Meta:
        model = Story
        fields = ["guid", "property", "media", "views"]

    def get_media(self, obj):
        request = self.context["request"]
        media_id = self.context["media_id"]

        media = obj.media.filter(guid=media_id).first()
        if not media:
            raise serializers.ValidationError("Media not found")

        return StoryMediaSerializer(media, context={"request": request}).data

    def get_views(self, obj):
        cache_key = f"story:{obj.guid}:views"
        count = int(cache.get(cache_key) or 0)
        return obj.views + count


class StoryCreateSerializer(serializers.Serializer):
    property_id = serializers.UUIDField(required=True)
    media_type = serializers.CharField(required=True)
    media_file = serializers.FileField(required=True)

    def validate_property_id(self, value):
        request = self.context["request"]
        partner = getattr(request, "user")

        property = Property.objects.filter(guid=value).first()
        if not property:
            raise serializers.ValidationError(_("Property not found"))

        if property.partner != partner:
            raise serializers.ValidationError("You don't own this property")

        return value

    def validate(self, attrs):
        media_type = attrs["media_type"]
        media_file = attrs["media_file"]

        extension = media_file.name.split(".")[-1].lower()
        if media_type == "image":
            if extension not in settings.ALLOWED_PHOTO_EXTENSION:
                raise serializers.ValidationError(
                    {
                        "media_file": _(
                            "Invalid image format, allowed are: jpg, jpeg, png, heif, heic"
                        )
                    }
                )

            if media_file.size > settings.MAX_IMAGE_SIZE:
                raise serializers.ValidationError(
                    {"media_file": _("Image file too large, maximum size is 20MB")}
                )

        elif media_type == "video":
            if extension not in settings.ALLOWED_VIDEO_EXTENSION:
                raise serializers.ValidationError(
                    {
                        "media_file": _(
                            "Invalid video format, allowed are: mp4, mov, avi, mkv"
                        )
                    }
                )

            if media_file.size > settings.MAX_VIDEO_SIZE:
                raise serializers.ValidationError(
                    {"media_file": _("Video file too large, maximum size is 100MB")}
                )

        else:
            raise serializers.ValidationError(
                {"media_type": _("Unsupported media type")}
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        partner = getattr(request, "user")
        property_id = self.validated_data["property_id"]
        property = Property.objects.filter(guid=property_id, partner=partner).first()

        if not property:
            raise serializers.ValidationError({"property_id": _("Property not found")})

        story = Story.objects.filter(
            property=property, expires_at__gt=timezone.now()
        ).first()

        if not story:
            story = Story.objects.create(property=property)

        media_type = validated_data["media_type"]
        media_file = validated_data["media_file"]

        StoryMedia.objects.create(
            story=story,
            media=media_file,
            media_type=media_type,
        )

        return story

    def to_representation(self, instance):
        return StorySerializer(instance, context=self.context).data
