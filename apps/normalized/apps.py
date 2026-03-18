from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NormalizedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "normalized"
    verbose_name = _("Normalized Shadow Schema")

    def ready(self):
        from . import signals  # noqa: F401
