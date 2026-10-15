"""Loyalty levels ("Мой статус"): configured per business, progress by card spend_total."""
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.wallet import LoyaltyTierInfo


def parse_tiers(raw: list[dict[str, Any]] | None) -> list[tuple[int, str | None, Decimal, Decimal]]:
    """Return (level, name, threshold, percent) sorted by threshold; malformed rows are skipped."""
    tiers: list[tuple[int, str | None, Decimal, Decimal]] = []
    for row in raw or []:
        if not isinstance(row, dict):
            continue
        try:
            level = int(row["level"])
            threshold = Decimal(str(row["threshold"]))
            percent = Decimal(str(row["percent"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
        name = row.get("name")
        tiers.append((level, name if isinstance(name, str) and name else None, threshold, percent))
    return sorted(tiers, key=lambda tier: (tier[2], tier[0]))


def tier_info(raw_tiers: list[dict[str, Any]] | None, spend_total: Decimal | None) -> LoyaltyTierInfo | None:
    """Current level and progress to the next one, or None when the business has no levels."""
    tiers = parse_tiers(raw_tiers)
    if not tiers:
        return None
    spend = spend_total if spend_total is not None else Decimal(0)
    current_index = 0
    for index, tier in enumerate(tiers):
        if spend >= tier[2]:
            current_index = index
    level, name, _threshold, percent = tiers[current_index]
    next_tier = tiers[current_index + 1] if current_index + 1 < len(tiers) else None
    return LoyaltyTierInfo(
        level=level,
        name=name,
        percent=percent,
        max_percent=max(tier[3] for tier in tiers),
        spend_total=spend_total,
        next_level=next_tier[0] if next_tier else None,
        next_threshold=next_tier[2] if next_tier else None,
        remaining=max(next_tier[2] - spend, Decimal(0)) if next_tier else None,
    )
