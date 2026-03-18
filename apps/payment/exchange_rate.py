from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.cache import cache
from django.db.utils import ProgrammingError
from django.utils.translation import gettext_lazy as _

from rest_framework.exceptions import ValidationError

from .models import ExchangeRate


def _rate_from_norm_today():
    from norm_store.models import NormExchangeRate

    return NormExchangeRate.objects.filter(currency="USD", date=date.today()).first()


def _rate_from_norm_latest():
    from norm_store.models import NormExchangeRate

    return (
        NormExchangeRate.objects.filter(currency="USD")
        .only("rate", "date")
        .order_by("-date")
        .first()
    )


def exchange_rate():
    rate = cache.get("usd_to_uzs_rate")
    if rate:
        return rate

    use_norm = getattr(settings, "USE_NORM_DATASTORE", False)

    # 1) Prefer norm tables if enabled (or if legacy table is missing)
    if use_norm:
        record = _rate_from_norm_today()
        if record:
            cache.set("usd_to_uzs_rate", record.rate, timeout=86400)
            return record.rate
        latest_record = _rate_from_norm_latest()
        if latest_record:
            cache.set("usd_to_uzs_rate", latest_record.rate, timeout=3600)
            return latest_record.rate

    # 2) Legacy ExchangeRate table (may not exist in production)
    try:
        record = ExchangeRate.objects.filter(currency="USD", date=date.today()).first()
        if record:
            cache.set("usd_to_uzs_rate", record.rate, timeout=86400)
            return record.rate
        latest_record = (
            ExchangeRate.objects.filter(currency="USD")
            .only("rate", "date")
            .order_by("-date")
            .first()
        )
        if latest_record:
            cache.set("usd_to_uzs_rate", latest_record.rate, timeout=3600)
            return latest_record.rate
    except ProgrammingError:
        # Missing legacy table → fallback to norm even if USE_NORM_DATASTORE not set.
        record = _rate_from_norm_today()
        if record:
            cache.set("usd_to_uzs_rate", record.rate, timeout=86400)
            return record.rate
        latest_record = _rate_from_norm_latest()
        if latest_record:
            cache.set("usd_to_uzs_rate", latest_record.rate, timeout=3600)
            return latest_record.rate

    raise ValidationError(_("Exchange rate isn't synchronized today"))


def round_amount(amount: Decimal) -> Decimal:
    """
    Round amount to nearst 10,000 UZS
    - last 4 digits < 5000  round down
    - last 4 digits ≥ 5000 round up
    """

    amount = amount.quantize(Decimal("1"))
    remainder = amount % Decimal("10000")

    if remainder < Decimal("5000"):
        return amount - remainder
    else:
        return amount + (Decimal("10000") - remainder)


def to_uzs(amount: Decimal) -> Decimal:
    rate = exchange_rate()
    return round_amount(amount * rate)


def to_usd(amount: Decimal) -> Decimal:
    rate = exchange_rate()
    return (amount / rate).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
