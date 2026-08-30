from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
) -> dict[str, Any]:
    """Multi-signal distribution drift detector.

    Combines three complementary signals so that no single moment can be gamed:

    1. **Mean ratio** – catches location shifts (e.g. revenue suddenly 3× higher).
    2. **Variance ratio** – catches spread changes (e.g. variance explodes after
       injecting outliers even when mean is similar).
    3. **Median absolute deviation (MAD) ratio** – robust version of signal 2,
       insensitive to extreme outliers.

    The composite ``score`` is the maximum of the three individual scores, and
    ``is_anomaly`` is True when that maximum exceeds ``ratio_threshold``.

    For very small or degenerate inputs the detector degrades gracefully.
    """
    cur = np.asarray(list(current_values), dtype=float)
    base = np.asarray(list(baseline_values), dtype=float)

    if cur.size == 0 or base.size == 0:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "multi_signal",
            "reason": "empty_input",
        }

    cur_mean = float(np.mean(cur))
    base_mean = float(np.mean(base))

    # --- Signal 1: mean ratio ---
    if base_mean == 0:
        mean_ratio = float("inf") if cur_mean != 0 else 1.0
    else:
        mean_ratio = max(abs(cur_mean / base_mean), abs(base_mean / cur_mean)) if cur_mean != 0 else float("inf")

    # --- Signal 2: variance ratio ---
    cur_var = float(np.var(cur)) if cur.size > 1 else 0.0
    base_var = float(np.var(base)) if base.size > 1 else 0.0
    if base_var == 0:
        var_ratio = float("inf") if cur_var > 0 else 1.0
    else:
        var_ratio = max(cur_var / base_var, base_var / cur_var) if cur_var > 0 else float("inf")

    # --- Signal 3: MAD ratio (robust spread) ---
    cur_mad = float(np.median(np.abs(cur - np.median(cur))))
    base_mad = float(np.median(np.abs(base - np.median(base))))
    if base_mad == 0:
        mad_ratio = float("inf") if cur_mad > 0 else 1.0
    else:
        mad_ratio = max(cur_mad / base_mad, base_mad / cur_mad) if cur_mad > 0 else float("inf")

    # Composite: worst-case signal wins
    composite_score = max(mean_ratio, var_ratio, mad_ratio)

    return {
        "is_anomaly": bool(composite_score >= ratio_threshold),
        "score": float(composite_score),
        "method": "multi_signal",
        "mean_ratio": float(mean_ratio),
        "variance_ratio": float(var_ratio),
        "mad_ratio": float(mad_ratio),
        "reason": (
            f"baseline_mean={base_mean:.3f}, current_mean={cur_mean:.3f}; "
            f"mean_ratio={mean_ratio:.2f}, var_ratio={var_ratio:.2f}, mad_ratio={mad_ratio:.2f}"
        ),
    }
