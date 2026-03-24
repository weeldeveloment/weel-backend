import copy
import json

from django import forms
from django.contrib import admin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin

from .models import (
    Apartment,
    Cottages,
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


class ApartmentInlinePermissionMixin:
    """Faqat Apartment inline'lari uchun ko'rsatish permissionlari."""

    def _is_staff(self, request):
        return bool(getattr(request, "user", None) and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        return self._is_staff(request)

    def has_view_or_change_permission(self, request, obj=None):
        return self._is_staff(request)

    def has_change_permission(self, request, obj=None):
        return self._is_staff(request)

    def has_add_permission(self, request, obj=None):
        return self._is_staff(request)

    def has_delete_permission(self, request, obj=None):
        return False


class CottageDetailInline(admin.StackedInline):
    """Cottages uchun detail fieldlari."""

    model = PropertyDetail
    extra = 1
    max_num = 1
    can_delete = False
    fields = [
        ("description_uz", "description_ru", "description_en"),
        ("check_in", "check_out"),
        ("home_number", "pass_code"),
        (
            "is_quiet_hours",
            "is_allowed_alcohol",
            "is_allowed_corporate",
            "is_allowed_pets",
        ),
    ]


class ApartmentDetailInline(ApartmentInlinePermissionMixin, admin.StackedInline):
    """Apartment uchun detail fieldlari."""

    model = PropertyDetail
    extra = 1
    max_num = 1
    can_delete = False
    verbose_name_plural = _("Kvartira ma'lumotlari")
    fieldsets = [
        (
            _("Kvartira ma'lumotlari"),
            {
                "fields": [
                    ("apartment_number", "home_number"),
                    ("entrance_number", "floor_number"),
                    "pass_code",
                ]
            },
        ),
        (
            _("Description"),
            {
                "fields": [
                    ("description_uz", "description_ru", "description_en"),
                ]
            },
        ),
        (
            _("Kvartira sozlamalari"),
            {
                "fields": [
                    ("check_in", "check_out"),
                    (
                        "is_quiet_hours",
                        "is_allowed_alcohol",
                        "is_allowed_corporate",
                        "is_allowed_pets",
                    ),
                ]
            },
        ),
    ]

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        form.base_fields["apartment_number"].required = True
        form.base_fields["home_number"].required = True
        form.base_fields["entrance_number"].required = True
        form.base_fields["floor_number"].required = True
        form.base_fields["pass_code"].required = True
        return formset


class CottageRoomInline(admin.TabularInline):
    """Cottages uchun xona/yotoq/hamom parametrlar."""

    model = PropertyRoom
    extra = 1
    max_num = 1
    can_delete = False
    fields = ("guests", "rooms", "beds", "bathrooms")


class ApartmentRoomInline(ApartmentInlinePermissionMixin, admin.TabularInline):
    """Apartment uchun xona/yotoq/hamom parametrlar."""

    model = PropertyRoom
    extra = 1
    max_num = 1
    can_delete = False
    fields = ("guests", "rooms", "beds", "bathrooms")


class CottagePriceInline(admin.TabularInline):
    """Cottages oylar bo'yicha narxlar."""

    model = PropertyPrice
    extra = 1
    fields = (
        "month_from",
        "month_to",
        "price_per_person",
        "price_on_working_days",
        "price_on_weekends",
    )


PROPERTY_DETAIL_ADMIN_PROPERTY_FIELDS = [
    "title",
    "property_type",
    "img",
    "currency",
    "price",
    "partner",
    "property_location",
    "region",
    "district",
    "shaharcha",
    "mahalla",
    "property_services",
    "categories",
    "minimum_weekend_day_stay",
    "weekend_only_sunday_inclusive",
    "verification_status",
    "is_verified",
    "verified_at",
    "verified_by",
    "is_recommended",
    "is_archived",
]
PROPERTY_DETAIL_ADMIN_M2M_FIELDS = ["property_services", "categories"]
PROPERTY_DETAIL_ADMIN_NON_M2M_FIELDS = [
    field for field in PROPERTY_DETAIL_ADMIN_PROPERTY_FIELDS
    if field not in PROPERTY_DETAIL_ADMIN_M2M_FIELDS
]
_PROPERTY_DETAIL_PROPERTY_FORM = forms.modelform_factory(
    Property, fields=PROPERTY_DETAIL_ADMIN_PROPERTY_FIELDS
)


class PropertyDetailAdminForm(forms.ModelForm):
    PROPERTY_M2M_FIELDS = PROPERTY_DETAIL_ADMIN_M2M_FIELDS
    PROPERTY_NON_M2M_FIELDS = PROPERTY_DETAIL_ADMIN_NON_M2M_FIELDS
    for _field_name in PROPERTY_DETAIL_ADMIN_PROPERTY_FIELDS:
        locals()[_field_name] = copy.deepcopy(
            _PROPERTY_DETAIL_PROPERTY_FORM.base_fields[_field_name]
        )
    del _field_name

    class Meta:
        model = PropertyDetail
        fields = [
            "property",
            "apartment_number",
            "home_number",
            "entrance_number",
            "floor_number",
            "pass_code",
            "description_uz",
            "description_ru",
            "description_en",
            "check_in",
            "check_out",
            "is_quiet_hours",
            "is_allowed_alcohol",
            "is_allowed_corporate",
            "is_allowed_pets",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        property_queryset = Property.objects.select_related("property_type")
        if self.instance and self.instance.pk and self.instance.property_id:
            property_queryset = property_queryset.filter(
                Q(property_detail__isnull=True) | Q(pk=self.instance.property_id)
            )
        else:
            property_queryset = property_queryset.filter(property_detail__isnull=True)
        self.fields["property"].queryset = property_queryset

        property_obj = None
        if self.instance and self.instance.pk and self.instance.property_id:
            property_obj = self.instance.property
            for field_name in PROPERTY_DETAIL_ADMIN_PROPERTY_FIELDS:
                if field_name in self.fields:
                    if field_name in self.PROPERTY_M2M_FIELDS:
                        self.fields[field_name].initial = getattr(
                            property_obj, field_name
                        ).all()
                    else:
                        self.fields[field_name].initial = getattr(property_obj, field_name)

        selected_property_type = None
        if self.is_bound:
            raw_property_type = (
                self.data.get(self.add_prefix("property_type"))
                or self.data.get("property_type")
            )
            if raw_property_type:
                selected_property_type = (
                    PropertyType.objects.filter(pk=raw_property_type).first()
                    or PropertyType.objects.filter(guid=raw_property_type).first()
                )

            raw_property = (
                self.data.get(self.add_prefix("property"))
                or self.data.get("property")
            )
            if not selected_property_type and raw_property:
                selected_property = (
                    Property.objects.select_related("property_type")
                    .filter(pk=raw_property)
                    .first()
                    or Property.objects.select_related("property_type")
                    .filter(guid=raw_property)
                    .first()
                )
                if selected_property:
                    selected_property_type = selected_property.property_type

        if not selected_property_type and property_obj:
            selected_property_type = property_obj.property_type
        if selected_property_type:
            self.fields["property_services"].queryset = PropertyService.objects.filter(
                property_type=selected_property_type
            )

        if "verified_by" in self.fields:
            self.fields["verified_by"].required = False
        if "verified_at" in self.fields:
            self.fields["verified_at"].required = False

    def clean(self):
        data = super().clean()
        property_type = data.get("property_type")

        if data.get("is_verified") and data.get("verification_status") != VerificationStatus.ACCEPTED:
            data["verification_status"] = VerificationStatus.ACCEPTED

        if property_type and (property_type.title_en or "").strip().lower() == "apartment":
            apartment_required = [
                "apartment_number",
                "home_number",
                "entrance_number",
                "floor_number",
                "pass_code",
            ]
            for field_name in apartment_required:
                if not data.get(field_name):
                    self.add_error(
                        field_name,
                        _("This field is required for apartment properties."),
                    )

        region = data.get("region")
        district = data.get("district")
        shaharcha = data.get("shaharcha")
        if district and region and district.region_id != region.id:
            self.add_error("district", _("District must belong to the selected region."))
        if district and not region:
            data["region"] = district.region
        if shaharcha and district and shaharcha.district_id != district.id:
            self.add_error(
                "shaharcha",
                _("Shaharcha must belong to the selected district."),
            )
        if shaharcha and not district:
            data["district"] = shaharcha.district
            data["region"] = shaharcha.district.region

        title = data.get("title")
        property_obj = data.get("property") or getattr(self.instance, "property", None)
        if title:
            exists_qs = Property.objects.filter(title=title, is_archived=False)
            if property_obj and property_obj.pk:
                exists_qs = exists_qs.exclude(pk=property_obj.pk)
            if exists_qs.exists():
                self.add_error("title", _("Property with this title already exists."))

        return data


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
        "is_verified",
        "is_recommended",
        "created_at",
    ]
    list_filter = ["property_type", "is_verified", "is_recommended", "created_at"]
    filter_horizontal = ["property_services", "categories"]

    inlines = [PropertyImageInline]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }

    def _resolve_property_type_title(self, request, obj=None):
        if obj and getattr(obj, "property_type_id", None):
            return (obj.property_type.title_en or "").strip().lower()

        raw_property_type = request.POST.get("property_type") or request.GET.get("property_type")
        if raw_property_type:
            property_type = (
                PropertyType.objects.filter(pk=raw_property_type).only("title_en").first()
                or PropertyType.objects.filter(guid=raw_property_type).only("title_en").first()
            )
            if property_type:
                return (property_type.title_en or "").strip().lower()

        resolver_match = getattr(request, "resolver_match", None)
        object_id = resolver_match.kwargs.get("object_id") if resolver_match else None
        if object_id:
            prop = (
                Property.objects.select_related("property_type")
                .filter(pk=object_id)
                .only("property_type__title_en")
                .first()
            )
            if prop and prop.property_type:
                return (prop.property_type.title_en or "").strip().lower()

        return ""

    def _apartment_fieldsets(self):
        return [
            (
                _("Apartment info"),
                {
                    "fields": [
                        "title",
                        "property_type",
                        "img",
                        "currency",
                        "price",
                        "partner",
                    ]
                },
            ),
            (
                _("Location"),
                {
                    "fields": [
                        "property_location",
                        "region",
                        "district",
                        "shaharcha",
                        "mahalla",
                    ]
                },
            ),
            (
                _("Services"),
                {"fields": ["property_services", "categories"]},
            ),
            (
                _("Booking rules"),
                {"fields": ["minimum_weekend_day_stay", "weekend_only_sunday_inclusive"]},
            ),
            (
                _("Verification"),
                {"fields": ["verification_status", "is_verified", "verified_at", "verified_by"]},
            ),
            (
                _("Visibility"),
                {"fields": ["is_recommended", "is_archived"]},
            ),
        ]

    def _cottages_fieldsets(self):
        return [
            (
                _("Cottage info"),
                {
                    "fields": [
                        "title",
                        "property_type",
                        "img",
                        "currency",
                        "partner",
                    ]
                },
            ),
            (
                _("Location"),
                {
                    "fields": [
                        "property_location",
                        "region",
                        "district",
                        "shaharcha",
                        "mahalla",
                    ]
                },
            ),
            (
                _("Services"),
                {"fields": ["property_services", "categories"]},
            ),
            (
                _("Booking rules"),
                {"fields": ["minimum_weekend_day_stay", "weekend_only_sunday_inclusive"]},
            ),
            (
                _("Verification"),
                {"fields": ["verification_status", "is_verified", "verified_at", "verified_by"]},
            ),
            (
                _("Visibility"),
                {"fields": ["is_recommended", "is_archived"]},
            ),
        ]

    def get_fieldsets(self, request, obj=None):
        # Faqat umumiy Property adminda type bo'yicha dinamik fieldset ishlaydi.
        if self.__class__ is not PropertyAdmin:
            return super().get_fieldsets(request, obj)

        property_type_title = self._resolve_property_type_title(request, obj=obj)
        if property_type_title == "apartment":
            return self._apartment_fieldsets()
        if property_type_title == "cottages":
            return self._cottages_fieldsets()
        return super().get_fieldsets(request, obj)

    def get_inlines(self, request, obj):
        # Faqat umumiy Property adminda type bo'yicha dinamik inline ishlaydi.
        if self.__class__ is not PropertyAdmin:
            return super().get_inlines(request, obj)

        property_type_title = self._resolve_property_type_title(request, obj=obj)
        if property_type_title == "apartment":
            return [ApartmentDetailInline, ApartmentRoomInline, PropertyImageInline]
        if property_type_title == "cottages":
            return [PropertyImageInline, CottageDetailInline, CottageRoomInline, CottagePriceInline]
        return [PropertyImageInline]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if self.__class__ is PropertyAdmin and db_field.name == "property_services":
            property_type_title = self._resolve_property_type_title(request)
            if property_type_title:
                property_type = PropertyType.objects.filter(
                    title_en__iexact=property_type_title
                ).first()
                if property_type:
                    kwargs["queryset"] = PropertyService.objects.filter(
                        property_type=property_type
                    )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

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


class TypeRestrictedPropertyAdmin(PropertyAdmin):
    """Property type bo'yicha qat'iy ajratilgan admin (Apartment/Cottages)."""

    property_type_title_en = None

    def _get_property_type(self):
        if not self.property_type_title_en:
            return None
        return PropertyType.objects.filter(
            title_en__iexact=self.property_type_title_en
        ).first()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not self.property_type_title_en:
            return qs
        return qs.filter(property_type__title_en__iexact=self.property_type_title_en)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "property_type":
            property_type = self._get_property_type()
            if property_type:
                kwargs["queryset"] = PropertyType.objects.filter(pk=property_type.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "property_services":
            property_type = self._get_property_type()
            if property_type:
                kwargs["queryset"] = PropertyService.objects.filter(
                    property_type=property_type
                )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        property_type = self._get_property_type()
        if property_type:
            obj.property_type = property_type
        super().save_model(request, obj, form, change)


@admin.register(Apartment)
class ApartmentAdmin(TypeRestrictedPropertyAdmin):
    """Admin: faqat Apartment tipidagi propertylar."""

    property_type_title_en = "Apartment"
    inlines = [ApartmentDetailInline, ApartmentRoomInline, PropertyImageInline]
    list_display = [
        "guid",
        "title",
        "apartment_number_display",
        "price",
        "currency",
        "region",
        "district",
        "shaharcha",
        "verification_status",
        "is_verified",
        "verified_at",
        "verified_by",
        "is_recommended",
        "created_at",
    ]
    list_filter = [
        "verification_status",
        "is_verified",
        "verified_by",
        "is_recommended",
        "region",
        "district",
        "created_at",
    ]
    fieldsets = [
        (
            _("Apartment info"),
            {
                "fields": [
                    "title",
                    "property_type",
                    "img",
                    "currency",
                    "price",
                    "partner",
                ]
            },
        ),
        (
            _("Location"),
            {
                "fields": [
                    "property_location",
                    "region",
                    "district",
                    "shaharcha",
                    "mahalla",
                ]
            },
        ),
        (
            _("Services"),
            {
                "fields": [
                    "property_services",
                    "categories",
                ]
            },
        ),
        (
            _("Booking rules"),
            {
                "fields": [
                    "minimum_weekend_day_stay",
                    "weekend_only_sunday_inclusive",
                ]
            },
        ),
        (
            _("Verification"),
            {
                "fields": [
                    "verification_status",
                    "is_verified",
                    "verified_at",
                    "verified_by",
                ]
            },
        ),
        (
            _("Visibility"),
            {
                "fields": [
                    "is_recommended",
                    "is_archived",
                ]
            },
        ),
    ]

    @admin.display(description=_("Apartment #"))
    def apartment_number_display(self, obj):
        detail = getattr(obj, "property_detail", None)
        if detail:
            return detail.apartment_number or "—"
        return "—"


@admin.register(Cottages)
class CottagesAdmin(TypeRestrictedPropertyAdmin):
    """Admin: faqat Cottages tipidagi propertylar."""

    property_type_title_en = "Cottages"
    inlines = [PropertyImageInline, CottageDetailInline, CottageRoomInline, CottagePriceInline]
    list_display = [
        "guid",
        "title",
        "home_number_display",
        "currency",
        "region",
        "district",
        "shaharcha",
        "verification_status",
        "is_verified",
        "verified_at",
        "verified_by",
        "is_recommended",
        "created_at",
    ]
    list_filter = [
        "verification_status",
        "is_verified",
        "verified_by",
        "is_recommended",
        "region",
        "district",
        "created_at",
    ]
    fieldsets = [
        (
            _("Cottage info"),
            {
                "fields": [
                    "title",
                    "property_type",
                    "img",
                    "currency",
                    "partner",
                ]
            },
        ),
        (
            _("Location"),
            {
                "fields": [
                    "property_location",
                    "region",
                    "district",
                    "shaharcha",
                    "mahalla",
                ]
            },
        ),
        (
            _("Services"),
            {
                "fields": [
                    "property_services",
                    "categories",
                ]
            },
        ),
        (
            _("Booking rules"),
            {
                "fields": [
                    "minimum_weekend_day_stay",
                    "weekend_only_sunday_inclusive",
                ]
            },
        ),
        (
            _("Verification"),
            {
                "fields": [
                    "verification_status",
                    "is_verified",
                    "verified_at",
                    "verified_by",
                ]
            },
        ),
        (
            _("Visibility"),
            {
                "fields": [
                    "is_recommended",
                    "is_archived",
                ]
            },
        ),
    ]

    @admin.display(description=_("Home #"))
    def home_number_display(self, obj):
        detail = getattr(obj, "property_detail", None)
        if detail:
            return detail.home_number or "—"
        return "—"


@admin.register(PropertyDetail)
class PropertyDetailAdmin(ModelAdmin):
    COTTAGE_HIDDEN_PROPERTY_FIELDS = [
        "verification_status",
        "is_verified",
        "verified_at",
        "verified_by",
        "is_recommended",
        "is_archived",
    ]
    form = PropertyDetailAdminForm
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = [
        "guid",
        "property_title",
        "property_type_display",
        "price_display",
        "verification_status_display",
        "is_verified_display",
        "created_at",
    ]
    list_filter = [
        "property__property_type",
        "property__verification_status",
        "property__is_verified",
        "created_at",
    ]
    search_fields = [
        "property__title",
        "apartment_number",
        "home_number",
        "pass_code",
    ]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }

    @admin.display(description=_("Title"))
    def property_title(self, obj):
        return getattr(obj.property, "title", "—")

    @admin.display(description=_("Property type"))
    def property_type_display(self, obj):
        property_type = getattr(obj.property, "property_type", None)
        return property_type.title_en if property_type else "—"

    @admin.display(description=_("Price"))
    def price_display(self, obj):
        return getattr(obj.property, "price", None)

    @admin.display(description=_("Verification status"))
    def verification_status_display(self, obj):
        return getattr(obj.property, "verification_status", "—")

    @admin.display(description=_("Verified"))
    def is_verified_display(self, obj):
        return getattr(obj.property, "is_verified", False)

    def _resolve_property_type_title(self, request, obj=None):
        if obj and getattr(obj, "property_id", None):
            return (obj.property.property_type.title_en or "").strip().lower()

        raw_property = request.POST.get("property") or request.GET.get("property")
        if raw_property:
            selected_property = (
                Property.objects.select_related("property_type").filter(pk=raw_property).first()
                or Property.objects.select_related("property_type")
                .filter(guid=raw_property)
                .first()
            )
            if selected_property and selected_property.property_type:
                return (selected_property.property_type.title_en or "").strip().lower()

        raw_property_type = request.POST.get("property_type") or request.GET.get("property_type")
        if raw_property_type:
            property_type = (
                PropertyType.objects.filter(pk=raw_property_type).only("title_en").first()
                or PropertyType.objects.filter(guid=raw_property_type).only("title_en").first()
            )
            if property_type:
                return (property_type.title_en or "").strip().lower()

        resolver_match = getattr(request, "resolver_match", None)
        object_id = resolver_match.kwargs.get("object_id") if resolver_match else None
        if object_id:
            detail = (
                PropertyDetail.objects.select_related("property__property_type")
                .filter(pk=object_id)
                .only("property__property_type__title_en")
                .first()
            )
            if detail and detail.property and detail.property.property_type:
                return (detail.property.property_type.title_en or "").strip().lower()

        return ""

    def _apartment_fieldsets(self):
        return [
            (
                _("Apartment info"),
                {
                    "fields": [
                        "property",
                        "title",
                        "property_type",
                        "img",
                        "currency",
                        "price",
                        "partner",
                    ]
                },
            ),
            (
                _("Location"),
                {
                    "fields": [
                        "property_location",
                        "region",
                        "district",
                        "shaharcha",
                        "mahalla",
                    ]
                },
            ),
            (
                _("Services"),
                {"fields": ["property_services", "categories"]},
            ),
            (
                _("Booking rules"),
                {"fields": ["minimum_weekend_day_stay", "weekend_only_sunday_inclusive"]},
            ),
            (
                _("Verification"),
                {"fields": ["verification_status", "is_verified", "verified_at", "verified_by"]},
            ),
            (
                _("Visibility"),
                {"fields": ["is_recommended", "is_archived"]},
            ),
            (
                _("Kvartira ma'lumotlari"),
                {
                    "fields": [
                        ("apartment_number", "home_number"),
                        ("entrance_number", "floor_number"),
                        "pass_code",
                    ]
                },
            ),
            (
                _("Description"),
                {
                    "fields": [
                        ("description_uz", "description_ru", "description_en"),
                    ]
                },
            ),
            (
                _("Kvartira sozlamalari"),
                {
                    "fields": [
                        ("check_in", "check_out"),
                        (
                            "is_quiet_hours",
                            "is_allowed_alcohol",
                            "is_allowed_corporate",
                            "is_allowed_pets",
                        ),
                    ]
                },
            ),
        ]

    def _cottages_fieldsets(self):
        return [
            (
                _("Cottage info"),
                {
                    "fields": [
                        "property",
                        "title",
                        "property_type",
                        "img",
                        "currency",
                        "price",
                        "partner",
                    ]
                },
            ),
            (
                _("Location"),
                {
                    "fields": [
                        "property_location",
                        "region",
                        "district",
                        "shaharcha",
                        "mahalla",
                    ]
                },
            ),
            (
                _("Services"),
                {"fields": ["property_services", "categories"]},
            ),
            (
                _("Booking rules"),
                {"fields": ["minimum_weekend_day_stay", "weekend_only_sunday_inclusive"]},
            ),
            (
                _("Cottage detail"),
                {
                    "fields": [
                        ("home_number", "pass_code"),
                        ("description_uz", "description_ru", "description_en"),
                        ("check_in", "check_out"),
                        (
                            "is_quiet_hours",
                            "is_allowed_alcohol",
                            "is_allowed_corporate",
                            "is_allowed_pets",
                        ),
                    ]
                },
            ),
        ]

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        property_type_title = self._resolve_property_type_title(request, obj=obj)
        if property_type_title != "cottages":
            return form_class

        class CottageForm(form_class):
            pass

        for field_name in self.COTTAGE_HIDDEN_PROPERTY_FIELDS:
            CottageForm.base_fields.pop(field_name, None)
        return CottageForm

    def get_fieldsets(self, request, obj=None):
        property_type_title = self._resolve_property_type_title(request, obj=obj)
        if property_type_title == "apartment":
            return self._apartment_fieldsets()
        if property_type_title == "cottages":
            return self._cottages_fieldsets()
        return [
            (
                _("Property"),
                {
                    "fields": [
                        "property",
                        "title",
                        "property_type",
                        "img",
                        "currency",
                        "price",
                        "partner",
                        "property_location",
                        "region",
                        "district",
                        "shaharcha",
                        "mahalla",
                        "property_services",
                        "categories",
                        "minimum_weekend_day_stay",
                        "weekend_only_sunday_inclusive",
                        "verification_status",
                        "is_verified",
                        "verified_at",
                        "verified_by",
                        "is_recommended",
                        "is_archived",
                    ]
                },
            ),
            (
                _("Detail"),
                {
                    "fields": [
                        "apartment_number",
                        "home_number",
                        "entrance_number",
                        "floor_number",
                        "pass_code",
                        ("description_uz", "description_ru", "description_en"),
                        ("check_in", "check_out"),
                        "is_quiet_hours",
                        "is_allowed_alcohol",
                        "is_allowed_corporate",
                        "is_allowed_pets",
                    ]
                },
            ),
        ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        property_obj = obj.property
        for field_name in form.PROPERTY_NON_M2M_FIELDS:
            if field_name in form.cleaned_data:
                setattr(property_obj, field_name, form.cleaned_data[field_name])

        if property_obj.verification_status == VerificationStatus.ACCEPTED:
            if not property_obj.verified_by and request.user.is_staff:
                property_obj.verified_by = request.user
            if not property_obj.verified_at:
                property_obj.verified_at = timezone.now()

        property_obj.save()
        property_obj.property_services.set(form.cleaned_data.get("property_services", []))
        property_obj.categories.set(form.cleaned_data.get("categories", []))


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
