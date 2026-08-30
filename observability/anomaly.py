"""Anomaly detection module supporting Z-score, MAD, and context-aware auto detection.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    """Robust Median Absolute Deviation (MAD) detector handling zero-MAD edge cases."""
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    
    if mad == 0:
        # Fallback 1: Mean absolute deviation from median
        mean_ad = float(np.mean(np.abs(values - median)))
        if mean_ad > 0:
            modified_z = 0.6745 * abs(float(current) - median) / mean_ad
            return {
                "is_anomaly": bool(modified_z > threshold),
                "score": float(modified_z),
                "method": "mad",
                "reason": f"median={median:.3f}, mad_fallback_mean_ad={mean_ad:.3f}, threshold={threshold}",
            }
        # Fallback 2: Standard deviation
        std = float(np.std(values))
        if std > 0:
            score = abs(float(current) - median) / std
            return {
                "is_anomaly": bool(score > threshold),
                "score": float(score),
                "method": "mad",
                "reason": f"median={median:.3f}, mad_fallback_std={std:.3f}, threshold={threshold}",
            }
        # All values in history are identical
        score = float("inf") if float(current) != median else 0.0
        return {
            "is_anomaly": bool(score > threshold),
            "score": float(score),
            "method": "mad",
            "reason": f"median={median:.3f}, history_constant=True",
        }

    modified_z = 0.6745 * abs(float(current) - median) / mad
    return {
        "is_anomaly": bool(modified_z > threshold),
        "score": float(modified_z),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Context-aware anomaly detector."""
    hist_list = list(history)

    # Process context-based history filtering if available
    effective_history = hist_list
    context_applied: list[str] = []

    if context:
        if "same_segment_history" in context and context["same_segment_history"]:
            seg_hist = list(context["same_segment_history"])
            if len(seg_hist) >= 3:
                effective_history = seg_hist
                context_applied.append("same_segment_history")

        if "known_event" in context and context["known_event"]:
            # If known promotional/maintenance event, relax threshold or mark context
            context_applied.append(f"event={context['known_event']}")

    if method == "mad":
        return mad_detector(current, effective_history, threshold=threshold)

    if method == "zscore":
        return zscore_detector(current, effective_history, threshold=threshold)

    if method == "auto":
        # Smart selection: use robust MAD if history >= 5, else Z-score
        vals = np.asarray(effective_history, dtype=float)
        if vals.size >= 5:
            res = mad_detector(current, effective_history, threshold=threshold)
            res["method"] = "auto:mad"
        else:
            res = zscore_detector(current, effective_history, threshold=threshold)
            res["method"] = "auto:zscore"

        if context_applied:
            res["reason"] += f"; context=[{', '.join(context_applied)}]"
        return res

    raise ValueError(f"Unsupported method: {method}")
