"""
Commercial configuration for buyer-close packet generation.

Product code must not hardcode negotiation terms. Values here may be
overridden per deployment via environment variables. The legal and
reporting modules read values from this module exclusively.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return default if raw is None or raw == "" else raw


@dataclass(frozen=True)
class CommercialConfig:
    buyer_name:         str
    platform_name:      str
    support_days:       int
    validation_days:    int
    tranche_1_inr:      int
    tranche_1_display:  str
    tranche_2_inr:      int
    tranche_2_display:  str
    total_inr:          int
    total_display:      str
    seller_name:        str
    seller_address:     str
    seller_pan:         str
    seller_gstin:       str
    seller_email:       str
    seller_signatory:   str

    @property
    def shadow_eval_days(self) -> int:
        """Backward-compat alias for older text helpers."""
        return self.support_days

    @property
    def shadow_eval_fee(self) -> str:
        return self.tranche_1_display

    @property
    def asset_transfer_fee(self) -> str:
        return self.tranche_2_display


def load_commercial_config() -> CommercialConfig:
    return CommercialConfig(
        buyer_name        = _env_str(
            "PORTER_BUYER_NAME",
            "SmartShift Logistics Solutions Pvt Ltd (Porter)",
        ),
        platform_name     = _env_str(
            "PORTER_PLATFORM_NAME",
            "Porter Intelligence Platform",
        ),
        support_days      = _env_int("PORTER_SUPPORT_DAYS", 90),
        validation_days   = _env_int("PORTER_VALIDATION_DAYS", 90),
        tranche_1_inr     = _env_int("PORTER_TRANCHE_1_INR", 10_000_000),
        tranche_1_display = _env_str(
            "PORTER_TRANCHE_1_DISPLAY",
            "₹1,00,00,000 (₹1 crore)",
        ),
        tranche_2_inr     = _env_int("PORTER_TRANCHE_2_INR", 22_500_000),
        tranche_2_display = _env_str(
            "PORTER_TRANCHE_2_DISPLAY",
            "₹2,25,00,000 (₹2.25 crore)",
        ),
        total_inr         = _env_int("PORTER_TOTAL_INR", 32_500_000),
        total_display     = _env_str(
            "PORTER_TOTAL_DISPLAY",
            "₹3,25,00,000 (₹3.25 crore)",
        ),
        seller_name       = _env_str(
            "SELLER_ENTITY_NAME",
            "Porter Intelligence (Unregistered)",
        ),
        seller_address    = _env_str(
            "SELLER_ADDRESS",
            "[Seller registered address — to be confirmed on execution]",
        ),
        seller_pan        = _env_str(
            "SELLER_PAN",
            "[Seller PAN — to be confirmed on execution]",
        ),
        seller_gstin      = _env_str(
            "SELLER_GSTIN",
            "[Seller GSTIN if applicable]",
        ),
        seller_email      = _env_str(
            "SELLER_EMAIL",
            "arnav2580goyal@gmail.com",
        ),
        seller_signatory  = _env_str(
            "SELLER_SIGNATORY",
            "Arnav Goyal, Founder",
        ),
    )


COMMERCIAL = load_commercial_config()
