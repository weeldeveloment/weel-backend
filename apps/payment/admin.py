from django.contrib import admin

from unfold.admin import ModelAdmin

from .models import ExchangeRate

# Register your models here.
@admin.register(ExchangeRate)
class ExchangeRateAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    list_filter_submit = False
    list_display = ["guid", "currency", "rate", "date", "created_at"]

    readonly_preprocess_fields = {
        "model_field_name": "html.unescape",
        "other_field_name": lambda content: content.strip(),
    }
