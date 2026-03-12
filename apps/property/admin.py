import json

from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin

from .models import (
    Apartment,
    Property,
    PropertyType,
    PropertyRoom,
    PropertyPrice,
    PropertyImage,
    PropertyReview,
    PropertyDetail,
    PropertyService,
    Category,
    PropertyLocation,
    Region,
    District,
    Shaharcha,
    Mahalla,
)
from .models import VerificationStatus


# Register your models here.


@admin.register(PropertyType)
class PropertyTypeAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "get_localized_title", "created_at"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }

    def get_localized_title(self, obj):
        lang = get_language()
        title = f"title_{lang}"
        return getattr(obj, title, obj.title_ru)

    get_localized_title.short_description = _(f"Title")


@admin.register(PropertyService)
class PropertyServiceAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "get_localized_title", "property_type", "created_at"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }

    def get_localized_title(self, obj):
        lang = get_language()
        title = f"title_{lang}"
        return getattr(obj, title, obj.title_ru)

    get_localized_title.short_description = _(f"Title")


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["guid", "title_uz", "title_ru", "title_en", "created_at"]
    list_filter_submit = False
    search_fields = ["title_uz", "title_ru", "title_en"]


@admin.register(Region)
class RegionAdmin(ModelAdmin):
    list_display = ["guid", "title_uz", "title_ru", "title_en", "img", "created_at"]
    list_filter_submit = False


@admin.register(District)
class DistrictAdmin(ModelAdmin):
    list_display = ["guid", "title_uz", "region", "created_at"]
    list_filter = ["region"]
    list_filter_submit = False


class ShaharchaAdminForm(forms.ModelForm):
    """Viloyat tanlash → shu viloyatdagi tumanlar → yangi shaharcha nomlari (3 ta)."""

    region = forms.ModelChoiceField(
        queryset=Region.objects.all().order_by("title_uz"),
        required=False,
        label=_("Viloyat"),
        help_text=_("Avval viloyatni tanlang, keyin tuman roʻyxati filtrlanadi."),
    )

    class Meta:
        model = Shaharcha
        fields = ["district", "title_uz", "title_ru", "title_en"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["district"].label = _("Tuman")
        self.fields["district"].help_text = _(
            "Viloyatni tanlaganingizdan keyin shu viloyatdagi tumanlardan tanlang."
        )
        if self.instance and self.instance.pk and self.instance.district_id:
            self.fields["region"].initial = self.instance.district.region
        # Tartib: region, district, title_uz, title_ru, title_en
        order = ["region", "district", "title_uz", "title_ru", "title_en"]
        self.fields = type(self.fields)(
            (k, self.fields[k]) for k in order if k in self.fields
        )

    def clean(self):
        data = super().clean()
        region = data.get("region")
        district = data.get("district")
        if district and region and district.region_id != region.id:
            raise forms.ValidationError(
                _("Tanlangan tuman shu viloyatga tegishli emas.")
            )
        return data


@admin.register(Mahalla)
class MahallaAdmin(ModelAdmin):
    list_display = ["guid", "title_uz", "title_ru", "title_en", "created_at"]
    list_filter_submit = False
    search_fields = ["title_uz", "title_ru", "title_en"]
    ordering = ["title_uz"]


@admin.register(Shaharcha)
class ShaharchaAdmin(ModelAdmin):
    form = ShaharchaAdminForm
    list_display = ["guid", "title_uz", "district", "created_at"]
    list_filter = ["district__region", "district"]
    list_filter_submit = False
    change_form_template = "admin/property/shaharcha/change_form.html"
    fieldsets = [
        (
            None,
            {
                "fields": ["region", "district", "title_uz", "title_ru", "title_en"],
            },
        ),
    ]

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        # Viloyat maydonida plus/edit/view tugmalari bo‘lmasin — oddiy dropdown
        class WrapForm(form_class):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if "district" in self.fields and "region" in self.fields:
                    self.fields["region"].widget.attrs.update(
                        self.fields["district"].widget.attrs
                    )

        return WrapForm

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "get-districts/",
                self.admin_site.admin_view(self.get_districts_view),
                name="property_shaharcha_get-districts",
            ),
        ]
        return custom + urls

    def get_districts_view(self, request):
        """Viloyat bo‘yicha tumanlarni JSON qaytaradi (view orqali filtr)."""
        region_id = request.GET.get("region_id", "").strip()
        if not region_id:
            return JsonResponse([])
        try:
            from uuid import UUID
            UUID(region_id)
        except (ValueError, TypeError):
            return JsonResponse([])
        districts = list(
            District.objects.filter(region__guid=region_id)
            .order_by("title_uz")
            .values("guid", "title_uz")
        )
        data = [
            {"guid": str(d["guid"]), "title_uz": d["title_uz"]}
            for d in districts
        ]
        return JsonResponse(data)

    def _get_districts_by_region(self):
        """Har bir viloyat uchun tumanlar + viloyat tanlanmasa barcha tumanlar ("" kaliti)."""
        qs = (
            Region.objects.prefetch_related("districts")
            .order_by("title_uz")
        )
        by_region = {}
        for r in qs:
            dist_list = [
                {"pk": d.pk, "title_uz": d.title_uz}
                for d in r.districts.order_by("title_uz")
            ]
            # Region dropdown qiymati Django ModelChoiceField da pk (id) bo'ladi
            by_region[str(r.pk)] = dist_list
            by_region[str(r.guid)] = dist_list
            by_region[r.title_uz] = dist_list
        all_districts = [
            {"pk": d.pk, "title_uz": d.title_uz}
            for d in District.objects.select_related("region").order_by("region", "title_uz")
        ]
        by_region[""] = all_districts
        return by_region

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["districts_by_region"] = json.dumps(
            self._get_districts_by_region()
        )
        try:
            extra_context["get_districts_url"] = request.build_absolute_uri(
                reverse(
                    "admin:property_shaharcha_get-districts",
                    current_app=self.admin_site.name,
                )
            )
        except Exception:
            extra_context["get_districts_url"] = ""
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["districts_by_region"] = json.dumps(
            self._get_districts_by_region()
        )
        try:
            extra_context["get_districts_url"] = request.build_absolute_uri(
                reverse(
                    "admin:property_shaharcha_get-districts",
                    current_app=self.admin_site.name,
                )
            )
        except Exception:
            extra_context["get_districts_url"] = ""
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(PropertyLocation)
class PropertyLocationAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "longitude", "latitude", "country", "city", "created_at"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ("image", "order", "is_pending")
    readonly_fields = ("created_at",)
    show_change_link = True


class PropertyAdminForm(forms.ModelForm):
    """Verified / Accepted bo'lganda verified_by va verified_at ixtiyoriy — save_model da to'ldiriladi."""

    class Meta:
        model = Property
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Verified bo'lganda ham verified_by / verified_at bo'sh qolishi mumkin (save_model to'ldiradi)
        if "verified_by" in self.fields:
            self.fields["verified_by"].required = False
        if "verified_at" in self.fields:
            self.fields["verified_at"].required = False

    def clean(self):
        data = super().clean()
        status = data.get("verification_status")
        is_verified = data.get("is_verified")
        # "Verified" = Yes bo'lsa, verification_status ni Accepted qilamiz (model save() is_verified ni shundan oladi)
        if is_verified and status != VerificationStatus.ACCEPTED:
            data["verification_status"] = VerificationStatus.ACCEPTED
        return data


@admin.register(Property)
class PropertyAdmin(ModelAdmin):
    form = PropertyAdminForm
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = [
        "guid",
        "title",
        "property_type",
        "img",
        "price",
        "region",
        "district",
        "shaharcha",
        "mahalla",
        "is_verified",
        "is_recommended",
        "created_at",
    ]
    list_filter = ["property_type", "is_verified", "is_recommended", "mahalla", "created_at"]
    filter_horizontal = ["property_services", "categories"]

    inlines = [PropertyImageInline]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()

    def save_model(self, request, obj, form, change):
        # Verified = Yes (Accepted) bo'lganda verified_by va verified_at avtomatik to'ldiriladi
        if obj.verification_status == VerificationStatus.ACCEPTED:
            if not obj.verified_by and request.user.is_staff:
                obj.verified_by = request.user
            if not obj.verified_at:
                obj.verified_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(Apartment)
class ApartmentAdmin(PropertyAdmin):
    """Admin: faqat Apartment tipidagi propertylar."""

    list_display = [
        "guid",
        "title",
        "apartment_number_display",
        "price",
        "currency",
        "region",
        "district",
        "shaharcha",
        "is_verified",
        "is_recommended",
        "created_at",
    ]
    list_filter = ["is_verified", "is_recommended", "region", "district", "created_at"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(property_type__title_en="Apartment")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "property_type":
            from .models import PropertyType
            apartment_type = PropertyType.objects.filter(title_en="Apartment").first()
            if apartment_type:
                kwargs["queryset"] = PropertyType.objects.filter(pk=apartment_type.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:  # yangi qo'shilayotganda
            from .models import PropertyType
            apartment_type = PropertyType.objects.filter(title_en="Apartment").first()
            if apartment_type:
                obj.property_type = apartment_type
        super().save_model(request, obj, form, change)

    @admin.display(description=_("Apartment #"))
    def apartment_number_display(self, obj):
        detail = getattr(obj, "property_detail", None)
        if detail:
            return detail.apartment_number or "—"
        return "—"


@admin.register(PropertyPrice)
class PropertyPriceAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = [
        "guid",
        "property",
        "price_per_person",
        "price_on_working_days",
        "price_on_weekends",
        "month_from",
        "month_to",
        "created_at",
    ]
    list_filter = ["property__title", "created_at"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }


@admin.register(PropertyImage)
class PropertyImageAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "property", "image", "is_pending", "created_at"]
    list_filter = ["property", "is_pending"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }


@admin.register(PropertyDetail)
class PropertyDetailAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "property", "created_at"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }


@admin.register(PropertyRoom)
class PropertyRoomAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "guests", "rooms", "beds", "bathrooms"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }


@admin.register(PropertyReview)
class PropertyReviewAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "client", "property", "rating", "is_hidden", "created_at"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }
