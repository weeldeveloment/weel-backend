"""
Oʻzbekiston viloyatlari va tumanlari roʻyxatini yuklaydi.
Property qoʻshishda region/district tanlash va filter uchun ishlatiladi.

Ishlatish:
  python manage.py load_uz_regions_districts
  python manage.py load_uz_regions_districts --file apps/property/data/uz_regions_districts.json

Birinchi marta migratsiyani ishlatib, keyin bu commandni ishlating.
"""
import json
import os

from django.core.management.base import BaseCommand

from property.models import Region, District, Shaharcha


# Standart viloyat nomlari (Oʻzbekiston boʻylab)
DEFAULT_REGIONS = [
    {"title_uz": "Andijon", "title_ru": "Андижан", "title_en": "Andijan"},
    {"title_uz": "Buxoro", "title_ru": "Бухара", "title_en": "Bukhara"},
    {"title_uz": "Fargʻona", "title_ru": "Фергана", "title_en": "Fergana"},
    {"title_uz": "Jizzax", "title_ru": "Джизак", "title_en": "Jizzakh"},
    {"title_uz": "Namangan", "title_ru": "Наманган", "title_en": "Namangan"},
    {"title_uz": "Navoiy", "title_ru": "Навои", "title_en": "Navoiy"},
    {"title_uz": "Navoiy shahri", "title_ru": "Город Навои", "title_en": "Navoiy City"},
    {"title_uz": "Qashqadaryo", "title_ru": "Кашкадарья", "title_en": "Kashkadarya"},
    {"title_uz": "Qoraqalpogʻiston", "title_ru": "Каракалпакстан", "title_en": "Karakalpakstan"},
    {"title_uz": "Samarqand", "title_ru": "Самарканд", "title_en": "Samarkand"},
    {"title_uz": "Sirdaryo", "title_ru": "Сырдарья", "title_en": "Sirdaryo"},
    {"title_uz": "Surxondaryo", "title_ru": "Сурхандарья", "title_en": "Surkhandarya"},
    {"title_uz": "Toshkent", "title_ru": "Ташкентская область", "title_en": "Tashkent Region"},
    {"title_uz": "Toshkent shahri", "title_ru": "Город Ташкент", "title_en": "Tashkent City"},
    {"title_uz": "Xorazm", "title_ru": "Хорезм", "title_en": "Khorezm"},
]

# Har bir viloyat boʻyicha tumanlar (Wikipedia va rasmiy manbalar asosida)
DEFAULT_DISTRICTS_BY_REGION = {
    "Toshkent shahri": [
        "Akmal Ikromov", "Bektemir", "Chilonzor", "Hamza", "Mirobod", "Mirzo Ulugʻbek",
        "Olmazor", "Sergeli", "Shayxontohur", "Sobir Rahimov", "Uchtepa", "Yakkasaroy",
        "Yashnaobod", "Yunusobod",
    ],
    "Qoraqalpogʻiston": [
        "Amudaryo", "Beruniy", "Boʻzatov", "Chimboy", "Ellikqala", "Kegeyli", "Moʻynoq",
        "Nukus", "Qanlikoʻl", "Qoʻngʻirot", "Qoraoʻzak", "Shumanay", "Taxtakoʻpir",
        "Toʻrtkoʻl", "Xoʻjayli",
    ],
    "Andijon": [
        "Andijon", "Asaka", "Baliqchi", "Boʻzsuv", "Buloqboshi", "Izboskan", "Jalolquduq",
        "Marhamat", "Oltinkoʻl", "Paxtaobod", "Qoʻrgʻontepa", "Ulugʻnor", "Xoʻjaobod", "Xonobod",
    ],
    "Fargʻona": [
        "Beshariq", "Bogʻdod", "Buvayda", "Dangʻara", "Fargʻona", "Furqat", "Oltiariq",
        "Oxunboboev", "Oʻzbekiston", "Qoʻshtepa", "Quva", "Quvasoy", "Rishton", "Soʻx",
        "Toshloq", "Uchkoʻprik", "Yozyovon",
    ],
    "Namangan": [
        "Chortoq", "Chust", "Kosonsoy", "Mingbuloq", "Namangan", "Norin", "Pop",
        "Toʻraqoʻrgʻon", "Uchqoʻrgʻon", "Uychi", "Yangiqoʻrgʻon",
    ],
    "Toshkent": [
        "Angren", "Bekobod", "Boʻka", "Boʻstonliq", "Chinoz", "Chirchiq", "Ohangaron",
        "Olmaliq", "Oqqoʻrgʻon", "Oʻrtachirchiq", "Parkent", "Piskent", "Qibray",
        "Toshkent", "Yangiyoʻl", "Yuqorichirchiq", "Zangiota",
    ],
    "Samarqand": [
        "Bulungʻur", "Ishtixon", "Jomboy", "Kattaqoʻrgʻon", "Narpay", "Nurobod", "Oqdaryo",
        "Pastdargʻom", "Paxtachi", "Payariq", "Qoʻshrabot", "Samarqand", "Toyloq", "Urgut",
    ],
    "Buxoro": [
        "Buxoro", "Gʻijduvon", "Jondor", "Kogon", "Olot", "Peshku", "Qorakoʻl",
        "Qorovulbozor", "Romitan", "Shofirkon", "Vobkent",
    ],
    "Xorazm": [
        "Bogʻot", "Gurlan", "Hazorasp", "Pitnak", "Qoʻshkoʻpir", "Shovot", "Urganch",
        "Xiva", "Xonqa", "Yangiariq", "Yangibozor",
    ],
    "Surxondaryo": [
        "Angor", "Bandixon", "Boysun", "Denov", "Jarqoʻrgʻon", "Muzrabot", "Oltinsoy",
        "Qiziriq", "Qumqoʻrgʻon", "Sariosiyo", "Sherobod", "Shoʻrchi", "Termiz", "Uzun",
    ],
    "Qashqadaryo": [
        "Bahoriston", "Chiroqchi", "Dehqonobod", "Gʻuzor", "Kasbi", "Kitob", "Koson",
        "Muborak", "Nishon", "Qamashi", "Qarshi", "Shahrisabz", "Usmon Yusupov", "Yakkabogʻ",
    ],
    "Jizzax": [
        "Arnasoy", "Baxmal", "Doʻstlik", "Forish", "Gʻallaorol", "Jizzax", "Mirzachoʻl",
        "Paxtakor", "Yangiobod", "Zafarobod", "Zarbdor", "Zomin",
    ],
    "Sirdaryo": [
        "Baxt", "Boyovut", "Guliston", "Mehnatobod", "Mirzaobod", "Oqoltin", "Sayxunobod",
        "Sharof Rashidov", "Sirdaryo", "Xovos", "Yangiyer",
    ],
    "Navoiy": [
        "Karmana", "Konimex", "Navbahor", "Navoiy", "Nurota", "Qiziltepa", "Tomdi",
        "Uchquduq", "Xatirchi", "Zarafshon",
    ],
    "Navoiy shahri": [
        "Karmana",
    ],
}

# (region_title_uz, district_title_uz) -> shaharchalar roʻyxati (qoʻshimcha, Boʻstonliq kabi bir nechta shaharcha)
DEFAULT_SHAHARCHAS = {
    ("Toshkent", "Boʻstonliq"): [
        "G'azalkent",
        "Chimyon",
        "Burchmulla",
        "Qoraqoʻrgʻon",
        "Sijjak",
        "Oʻrtaovul",
        "Nureta",
        "Pskem",
    ],
}

# Har bir tuman uchun tuman markazi (Wikipedia: Oʻzbekiston:Tumanlar — Markaz ustuni)
# (region_title_uz, district_title_uz) -> markaz (bitta shaharcha)
TUMAN_MARKAZI = {
    ("Qoraqalpogʻiston", "Amudaryo"): "Mangʻit",
    ("Andijon", "Andijon"): "Kuyganyor",
    ("Surxondaryo", "Angor"): "Angor",
    ("Jizzax", "Arnasoy"): "Gʻoliblar",
    ("Andijon", "Asaka"): "Asaka",
    ("Qashqadaryo", "Bahoriston"): "Pomuq",
    ("Andijon", "Baliqchi"): "Baliqchi",
    ("Surxondaryo", "Bandixon"): "Bandixon",
    ("Jizzax", "Baxmal"): "Usmat",
    ("Toshkent", "Bekobod"): "Zafar",
    ("Qoraqalpogʻiston", "Beruniy"): "Beruniy",
    ("Fargʻona", "Beshariq"): "Beshariq",
    ("Fargʻona", "Bogʻdod"): "Bagʻdod",
    ("Xorazm", "Bogʻot"): "Bogʻot",
    ("Toshkent", "Boʻka"): "Boʻka",
    ("Sirdaryo", "Boyovut"): "Boyovut",
    ("Surxondaryo", "Boysun"): "Boysun",
    ("Qoraqalpogʻiston", "Boʻzatov"): "Qozonketkan",
    ("Andijon", "Boʻzsuv"): "Boʻz",
    ("Andijon", "Buloqboshi"): "Buloqboshi",
    ("Samarqand", "Bulungʻur"): "Bulungʻur",
    ("Fargʻona", "Buvayda"): "Yangiqoʻrgʻon",
    ("Buxoro", "Buxoro"): "Galaosiyo",
    ("Qoraqalpogʻiston", "Chimboy"): "Chimboy",
    ("Toshkent", "Chinoz"): "Chinoz",
    ("Qashqadaryo", "Chiroqchi"): "Chiroqchi",
    ("Namangan", "Chortoq"): "Chortoq",
    ("Namangan", "Chust"): "Chust",
    ("Fargʻona", "Dangʻara"): "Dangʻara",
    ("Qashqadaryo", "Dehqonobod"): "Karashina",
    ("Surxondaryo", "Denov"): "Denov",
    ("Jizzax", "Doʻstlik"): "Doʻstlik",
    ("Qoraqalpogʻiston", "Ellikqala"): "Boʻston",
    ("Fargʻona", "Fargʻona"): "Vodil",
    ("Jizzax", "Forish"): "Yangiqishloq",
    ("Fargʻona", "Furqat"): "Navbahor",
    ("Jizzax", "Gʻallaorol"): "Gʻallaorol",
    ("Buxoro", "Gʻijduvon"): "Gʻijduvon",
    ("Sirdaryo", "Guliston"): "Dehqonobod",
    ("Xorazm", "Gurlan"): "Gurlan",
    ("Qashqadaryo", "Gʻuzor"): "Gʻuzor",
    ("Xorazm", "Hazorasp"): "Hazorasp",
    ("Samarqand", "Ishtixon"): "Ishtixon",
    ("Andijon", "Izboskan"): "Poytugʻ",
    ("Andijon", "Jalolquduq"): "Jalaquduq",
    ("Surxondaryo", "Jarqoʻrgʻon"): "Jarqoʻrgʻon",
    ("Jizzax", "Jizzax"): "Uchtepa",
    ("Samarqand", "Jomboy"): "Jomboy",
    ("Buxoro", "Jondor"): "Jondor",
    ("Navoiy shahri", "Karmana"): "Karmana",
    ("Qashqadaryo", "Kasbi"): "Mugʻlon",
    ("Samarqand", "Kattaqoʻrgʻon"): "Payshanba",
    ("Qoraqalpogʻiston", "Kegeyli"): "Kegeyli",
    ("Qashqadaryo", "Kitob"): "Kitob",
    ("Buxoro", "Kogon"): "Kogon",
    ("Navoiy", "Konimex"): "Konimex",
    ("Qashqadaryo", "Koson"): "Koson",
    ("Namangan", "Kosonsoy"): "Kosonsoy",
    ("Andijon", "Marhamat"): "Marhamat",
    ("Sirdaryo", "Mehnatobod"): "Qahramon",
    ("Namangan", "Mingbuloq"): "Jomashoʻy",
    ("Jizzax", "Mirzachoʻl"): "Gagarin",
    ("Sirdaryo", "Mirzaobod"): "Navroʻz",
    ("Qoraqalpogʻiston", "Moʻynoq"): "Moʻynoq",
    ("Qashqadaryo", "Muborak"): "Muborak",
    ("Surxondaryo", "Muzrabot"): "Xalqobod",
    ("Namangan", "Namangan"): "Toshbuloq",
    ("Samarqand", "Narpay"): "Oqtosh",
    ("Navoiy", "Navbahor"): "Beshrabot",
    ("Navoiy", "Navoiy"): "Navoiy",
    ("Qashqadaryo", "Nishon"): "Yangi Nishon",
    ("Namangan", "Norin"): "Haqqulobod",
    ("Qoraqalpogʻiston", "Nukus"): "Oqmangʻit",
    ("Samarqand", "Nurobod"): "Nurobod",
    ("Navoiy", "Nurota"): "Nurota",
    ("Toshkent", "Ohangaron"): "Ohangaron",
    ("Buxoro", "Olot"): "Olot",
    ("Fargʻona", "Oltiariq"): "Oltiariq",
    ("Andijon", "Oltinkoʻl"): "Oltinkoʻl",
    ("Surxondaryo", "Oltinsoy"): "Qarluq",
    ("Samarqand", "Oqdaryo"): "Loyish",
    ("Sirdaryo", "Oqoltin"): "Sardoba",
    ("Toshkent", "Oqqoʻrgʻon"): "Oqqoʻrgʻon",
    ("Toshkent", "Oʻrtachirchiq"): "Toʻytepa",
    ("Fargʻona", "Oxunboboev"): "Langar",
    ("Fargʻona", "Oʻzbekiston"): "Yaypan",
    ("Toshkent", "Parkent"): "Parkent",
    ("Samarqand", "Pastdargʻom"): "Juma",
    ("Samarqand", "Paxtachi"): "Ziyodin",
    ("Jizzax", "Paxtakor"): "Paxtakor",
    ("Andijon", "Paxtaobod"): "Paxtaobod",
    ("Samarqand", "Payariq"): "Payariq",
    ("Buxoro", "Peshku"): "Yangibozor",
    ("Toshkent", "Piskent"): "Piskent",
    ("Namangan", "Pop"): "Pop",
    ("Qashqadaryo", "Qamashi"): "Qamashi",
    ("Qoraqalpogʻiston", "Qanlikoʻl"): "Qanlikoʻl",
    ("Qashqadaryo", "Qarshi"): "Beshkent",
    ("Toshkent", "Qibray"): "Qibray",
    ("Navoiy", "Qiziltepa"): "Qiziltepa",
    ("Surxondaryo", "Qiziriq"): "Sariq",
    ("Qoraqalpogʻiston", "Qoʻngʻirot"): "Qoʻngʻirot",
    ("Buxoro", "Qorakoʻl"): "Qorakoʻl",
    ("Qoraqalpogʻiston", "Qoraoʻzak"): "Qoraoʻzak",
    ("Andijon", "Qoʻrgʻontepa"): "Qoʻrgʻontepa",
    ("Buxoro", "Qorovulbozor"): "Qorovulbozor",
    ("Xorazm", "Qoʻshkoʻpir"): "Qoʻshkoʻpir",
    ("Samarqand", "Qoʻshrabot"): "Qoʻshrabot",
    ("Fargʻona", "Qoʻshtepa"): "Langar",
    ("Surxondaryo", "Qumqoʻrgʻon"): "Qumqoʻrgʻon",
    ("Fargʻona", "Quva"): "Quva",
    ("Toshkent", "Quyichirchiq"): "Doʻstobod",
    ("Fargʻona", "Rishton"): "Rishton",
    ("Buxoro", "Romitan"): "Romitan",
    ("Samarqand", "Samarqand"): "Gulobod",
    ("Surxondaryo", "Sariosiyo"): "Sariosiyo",
    ("Sirdaryo", "Sayxunobod"): "Sayhun",
    ("Qashqadaryo", "Shahrisabz"): "Shahrisabz",
    ("Andijon", "Shahrixon"): "Shahrixon",
    ("Sirdaryo", "Sharof Rashidov"): "Paxtaobod",
    ("Surxondaryo", "Sherobod"): "Sherobod",
    ("Buxoro", "Shofirkon"): "Shofirkon",
    ("Surxondaryo", "Shoʻrchi"): "Shoʻrchi",
    ("Xorazm", "Shovot"): "Shovot",
    ("Qoraqalpogʻiston", "Shumanay"): "Shumanay",
    ("Sirdaryo", "Sirdaryo"): "Sirdaryo",
    ("Fargʻona", "Soʻx"): "Ravon",
    ("Qoraqalpogʻiston", "Taxtakoʻpir"): "Taxtakoʻpir",
    ("Surxondaryo", "Termiz"): "Termiz",
    ("Navoiy", "Tomdi"): "Tomdibuloq",
    ("Namangan", "Toʻraqoʻrgʻon"): "Toʻraqoʻrgʻon",
    ("Qoraqalpogʻiston", "Toʻrtkoʻl"): "Toʻrtkoʻl",
    ("Toshkent", "Toshkent"): "Keles",
    ("Fargʻona", "Toshloq"): "Toshloq",
    ("Samarqand", "Toyloq"): "Toyloq",
    ("Fargʻona", "Uchkoʻprik"): "Uchkoʻprik",
    ("Namangan", "Uchqoʻrgʻon"): "Uchqoʻrgʻon",
    ("Navoiy", "Uchquduq"): "Uchquduq",
    ("Andijon", "Ulugʻnor"): "Oqoltin",
    ("Xorazm", "Urganch"): "Qorovul",
    ("Samarqand", "Urgut"): "Urgut",
    ("Qashqadaryo", "Usmon Yusupov"): "Yangi Mirishkor",
    ("Namangan", "Uychi"): "Uychi",
    ("Surxondaryo", "Uzun"): "Uzun",
    ("Buxoro", "Vobkent"): "Vobkent",
    ("Navoiy", "Xatirchi"): "Yangirabod",
    ("Xorazm", "Xiva"): "Xiva",
    ("Andijon", "Xoʻjaobod"): "Xoʻjaobod",
    ("Qoraqalpogʻiston", "Xoʻjayli"): "Xoʻjayli",
    ("Xorazm", "Xonqa"): "Xonqa",
    ("Sirdaryo", "Xovos"): "Farhod",
    ("Namangan", "Yangiqoʻrgʻon"): "Yangiqoʻrgʻon",
    ("Qashqadaryo", "Yakkabogʻ"): "Yakkabogʻ",
    ("Xorazm", "Yangiariq"): "Yangiariq",
    ("Xorazm", "Yangibozor"): "Yangibozor",
    ("Jizzax", "Yangiobod"): "Balandchaqir",
    ("Toshkent", "Yangiyoʻl"): "Gulbahor",
    ("Fargʻona", "Yozyovon"): "Yozyovon",
    ("Toshkent", "Yuqorichirchiq"): "Yangibozor",
    ("Jizzax", "Zafarobod"): "Zafarobod",
    ("Toshkent", "Zangiota"): "Eshonguzar",
    ("Jizzax", "Zarbdor"): "Zarbdor",
    ("Jizzax", "Zomin"): "Zomin",
}


def load_from_dict(regions_data, districts_by_region, verbosity=1):
    """Regions va Districts ni yaratadi (yoki yangilaydi)."""
    region_by_title_uz = {}
    created_regions = 0
    for r in regions_data:
        obj, created = Region.objects.get_or_create(
            title_uz=r["title_uz"],
            defaults={"title_ru": r["title_ru"], "title_en": r["title_en"]},
        )
        region_by_title_uz[r["title_uz"]] = obj
        if created:
            created_regions += 1

    created_districts = 0
    for region_title_uz, district_names in districts_by_region.items():
        region = region_by_title_uz.get(region_title_uz)
        if not region:
            if verbosity > 0:
                print(f"Viloyat topilmadi (tumanlar uchun): {region_title_uz}")
            continue
        for name_uz in district_names:
            _, created = District.objects.get_or_create(
                region=region,
                title_uz=name_uz,
                defaults={"title_ru": name_uz, "title_en": name_uz},
            )
            if created:
                created_districts += 1

    return created_regions, created_districts


def _normalize_apostrophe(s):
    """Oʻzbek ʻ (U+02BB) va ASCII ' ni bitta belgiga keltiradi (qidiruv uchun)."""
    if not s:
        return s
    return str(s).replace("\u02bb", "'").replace("'", "'")


def _get_region_district(region_title_uz, district_title_uz, verbosity=1):
    """Viloyat va tumanni topadi (apostrof farqiga qarshi mustahkam). (region, district) yoki (None, None)."""
    region = Region.objects.filter(title_uz=region_title_uz).first()
    if not region:
        region = Region.objects.filter(
            title_uz__icontains=region_title_uz.replace("ʻ", "'")
        ).first()
    if not region:
        if verbosity > 0:
            print(f"Viloyat topilmadi (shaharchalar uchun): {region_title_uz}")
        return None, None
    district = District.objects.filter(
        region=region, title_uz=district_title_uz
    ).first()
    if not district:
        for variant in [
            district_title_uz.replace("\u02bb", "'"),
            district_title_uz.replace("'", "\u02bb"),
            _normalize_apostrophe(district_title_uz),
        ]:
            if variant == district_title_uz:
                continue
            district = District.objects.filter(
                region=region, title_uz=variant
            ).first()
            if district:
                break
    if not district and verbosity > 0:
        print(f"Tuman topilmadi: {district_title_uz!r} ({region_title_uz})")
    return region, district


def _add_shaharcha(district, name_uz):
    """Bitta shaharcha qoʻshadi, yangi yaratilgan boʻlsa True qaytaradi."""
    _, created = Shaharcha.objects.get_or_create(
        district=district,
        title_uz=name_uz,
        defaults={"title_ru": name_uz, "title_en": name_uz},
    )
    return created


def load_shaharchas(verbosity=1):
    """TUMAN_MARKAZI (har tuman markazi) va DEFAULT_SHAHARCHAS boʻyicha Shaharcha yaratadi."""
    created = 0
    for (region_title_uz, district_title_uz), markaz in TUMAN_MARKAZI.items():
        region, district = _get_region_district(
            region_title_uz, district_title_uz, verbosity
        )
        if district and markaz:
            if _add_shaharcha(district, markaz):
                created += 1
    for (region_title_uz, district_title_uz), names in DEFAULT_SHAHARCHAS.items():
        region, district = _get_region_district(
            region_title_uz, district_title_uz, verbosity
        )
        if not district:
            continue
        for name_uz in names:
            if _add_shaharcha(district, name_uz):
                created += 1
    return created


class Command(BaseCommand):
    help = "Oʻzbekiston viloyatlari va tumanlarini Region va District jadvallariga yuklaydi (filter va property uchun)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="JSON fayl yoʻli (boʻlmasa default roʻyxat ishlatiladi). Format: "
                 '{"regions": [{"title_uz","title_ru","title_en"}], "districts": [{"region_title_uz","title_uz",...}]}',
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Avval barcha Region va District ni oʻchirib, qayta yuklash (ehtiyotkorlik bilan).",
        )

    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)
        file_path = options.get("file")
        clear = options.get("clear", False)

        if clear:
            District.objects.all().delete()
            Region.objects.all().delete()
            if verbosity > 0:
                self.stdout.write("Region va District tozalandi.")

        if file_path:
            if not os.path.isfile(file_path):
                self.stderr.write(self.style.ERROR(f"Fayl topilmadi: {file_path}"))
                return
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            regions_data = data.get("regions", [])
            districts_data = data.get("districts", [])
            # districts: [{"region_title_uz": "...", "title_uz": "...", "title_ru": "...", "title_en": "..."}]
            region_by_title_uz = {}
            for r in regions_data:
                obj, created = Region.objects.get_or_create(
                    title_uz=r["title_uz"],
                    defaults={"title_ru": r.get("title_ru", r["title_uz"]), "title_en": r.get("title_en", r["title_uz"])},
                )
                region_by_title_uz[r["title_uz"]] = obj
            created_regions = sum(
                1 for r in regions_data
                if Region.objects.filter(title_uz=r["title_uz"]).count() == 1
            )
            created_districts = 0
            for d in districts_data:
                region = region_by_title_uz.get(d["region_title_uz"])
                if not region:
                    continue
                _, created = District.objects.get_or_create(
                    region=region,
                    title_uz=d["title_uz"],
                    defaults={
                        "title_ru": d.get("title_ru", d["title_uz"]),
                        "title_en": d.get("title_en", d["title_uz"]),
                    },
                )
                if created:
                    created_districts += 1
            if verbosity > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"JSON dan yuklandi: {len(regions_data)} viloyat, {len(districts_data)} tuman. "
                    f"Yangi: ~{created_districts} tuman."
                ))
            return

        created_regions, created_districts = load_from_dict(
            DEFAULT_REGIONS, DEFAULT_DISTRICTS_BY_REGION, verbosity=verbosity
        )
        created_shaharchas = load_shaharchas(verbosity=verbosity)
        if verbosity > 0:
            self.stdout.write(self.style.SUCCESS(
                f"Yuklandi: yangi {created_regions} viloyat, {created_districts} tuman, {created_shaharchas} shaharcha. "
                "GET /api/property/regions/ , GET /api/property/districts/?region_id=<guid> , "
                "GET /api/property/shaharchas/?district_id=<guid> orqali olish mumkin."
            ))
