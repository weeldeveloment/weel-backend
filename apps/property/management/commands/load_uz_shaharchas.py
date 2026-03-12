"""
Faqat shaharchalarni yuklaydi (Region va District allaqachon boʻlishi kerak).
Boʻstonliq va boshqa DEFAULT_SHAHARCHAS dagi tumanlar uchun shaharcha yozuvlari yaratiladi.

Ishlatish:
  python manage.py load_uz_shaharchas
"""
from property.management.commands.load_uz_regions_districts import load_shaharchas
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Shaharchalarni yuklaydi (region va tumanlar oldin load_uz_regions_districts orqali yuklangan boʻlishi kerak)."

    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)
        created = load_shaharchas(verbosity=verbosity)
        if verbosity > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Shaharchalar yuklandi: yangi {created} ta. "
                    "GET /api/property/shaharchas/?district_id=<tuman_guid> orqali tekshiring."
                )
            )
