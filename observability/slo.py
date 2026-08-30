from __future__ import annotations

from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "starter",
) -> dict[str, Any]:
    """Multi-window burn-rate alert policy (Google SRE Chapter 5 style).

    Uses two time windows to distinguish a transient spike from a sustained fast
    burn, reducing both false-positive and false-negative alert rates.

    Google SRE recommended thresholds (for a 30-day SLO):
      - Critical / Page immediately: short ≥ 14x AND long ≥ 14x
        → burns 2% error budget in 1 hour, very sustained
      - Warning / Ticket: short ≥ 6x AND long ≥ 6x
        → burns 5% error budget in 6 hours
      - Info / Watch: either window ≥ 3x
        → slow burn worth monitoring

    The ``policy`` parameter is preserved for backward-compatibility but the
    logic always applies the real multi-window algorithm.
    """
    # --- Tier 1: Critical — both windows burning fast ---
    # A transient spike will raise the short window but not the long window.
    if short_window_burn >= 14.0 and long_window_burn >= 14.0:
        return {
            "page": True,
            "severity": "critical",
            "reason": "multiwindow_fast_burn_sustained",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }

    # --- Tier 2: Warning — moderate sustained burn ---
    if short_window_burn >= 6.0 and long_window_burn >= 6.0:
        return {
            "page": True,
            "severity": "warning",
            "reason": "multiwindow_moderate_burn_sustained",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }

    # --- Tier 3: Info — slow burn or transient spike ---
    if short_window_burn >= 3.0 or long_window_burn >= 3.0:
        # Transient: short is high but long is calm → do not page
        is_transient = short_window_burn >= 3.0 and long_window_burn < 3.0
        return {
            "page": False,
            "severity": "info",
            "reason": "transient_spike" if is_transient else "slow_burn_watch",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }

    return {
        "page": False,
        "severity": "ok",
        "reason": "within_budget",
        "short_window_burn": short_window_burn,
        "long_window_burn": long_window_burn,
    }
