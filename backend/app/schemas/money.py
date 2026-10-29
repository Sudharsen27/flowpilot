"""Exact money handling for API payloads. Amounts never pass through float."""

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BeforeValidator, Field, PlainSerializer

from app.models.deal import DEAL_AMOUNT_DECIMAL_PLACES, DEAL_AMOUNT_MAX_DIGITS

_CENTS = Decimal(1).scaleb(-DEAL_AMOUNT_DECIMAL_PLACES)
# Largest value Numeric(14, 2) stores. Pydantic's max_digits ignores trailing zeros
# ("1000000000000.00" counts as one digit), so the bound is enforced explicitly.
MONEY_MAX = Decimal(10) ** (DEAL_AMOUNT_MAX_DIGITS - DEAL_AMOUNT_DECIMAL_PLACES) - _CENTS
_CURRENCY_PATTERN = re.compile(r"[A-Z]{3}")


def _parse_money(value: object) -> object:
    # JSON numbers with a fraction arrive as float; accept exact strings and integers only.
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError('Send amounts as a string, for example "1234.50"')
    if isinstance(value, str):
        cleaned = value.strip()
        try:
            value = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError("Enter a valid amount") from exc
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError("Enter a valid amount")
    return value


def format_money(value: Decimal) -> str:
    """Two-decimal string, e.g. Decimal('1234.5') -> '1234.50'."""
    return str(value.quantize(_CENTS))


Money = Annotated[
    Decimal,
    BeforeValidator(_parse_money),
    Field(
        ge=0,
        le=MONEY_MAX,
        max_digits=DEAL_AMOUNT_MAX_DIGITS,
        decimal_places=DEAL_AMOUNT_DECIMAL_PLACES,
        allow_inf_nan=False,
    ),
    PlainSerializer(format_money, return_type=str, when_used="json"),
]

# Read models: stored values are already valid, so only serialization applies.
MoneyOut = Annotated[Decimal, PlainSerializer(format_money, return_type=str, when_used="json")]


def normalize_currency(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    code = value.strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(code):
        raise ValueError("Currency must be a three-letter ISO 4217 code, for example INR")
    return code


CurrencyCode = Annotated[str, BeforeValidator(normalize_currency)]
