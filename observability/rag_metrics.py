from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from observability.anomaly import zscore_detector


def approximate_token_lengths(texts: Iterable[str]) -> list[int]:
    # Deliberately simple proxy; no tokenizer/model download needed.
    return [len(str(t).split()) for t in texts]


def detect_text_length_shift(
    current_texts: Iterable[str],
    baseline_batch_means: Iterable[float],
    *,
    threshold: float = 3.0,
) -> dict[str, Any]:
    lengths = approximate_token_lengths(current_texts)
    current_mean = float(np.mean(lengths)) if lengths else 0.0
    result = zscore_detector(current_mean, baseline_batch_means, threshold=threshold)
    result["metric"] = "mean_text_length"
    result["current_mean"] = current_mean
    return result


def detect_embedding_norm_shift(
    current_norms: Iterable[float], baseline_norms: Iterable[float]
) -> dict[str, Any]:
    """Detect embedding-space norm drift using robust z-score over norm distributions.

    No embedding model required — norms/cosine-similarities are fed in as
    pre-computed scalars.  The detector:
      1. Computes the mean L2-norm of the current batch.
      2. Compares it against the per-batch means of the baseline distribution
         using a MAD-based robust z-score so that outliers in the baseline do
         not mask real drift.
      3. Also reports a mean-ratio score for interpretability.

    Returns a dict with keys:
      is_anomaly (bool), score (float, z-score magnitude),
      method (str), ratio (float), current_mean (float), baseline_mean (float).
    """
    cur = np.asarray(list(current_norms), dtype=float)
    base = np.asarray(list(baseline_norms), dtype=float)

    if cur.size == 0 or base.size == 0:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "embedding_norm_zscore",
            "reason": "empty_input",
            "ratio": 1.0,
            "current_mean": 0.0,
            "baseline_mean": 0.0,
        }

    current_mean = float(np.mean(cur))
    baseline_mean = float(np.mean(base))

    # Robust z-score using MAD (median absolute deviation)
    baseline_median = float(np.median(base))
    mad = float(np.median(np.abs(base - baseline_median)))
    # Scale factor 1.4826 makes MAD consistent with std for normal distributions
    robust_std = 1.4826 * mad if mad > 0 else float(np.std(base)) + 1e-9

    z_score = abs(current_mean - baseline_mean) / robust_std

    # Mean ratio for interpretability
    if baseline_mean != 0:
        ratio = current_mean / baseline_mean
    else:
        ratio = float("inf") if current_mean != 0 else 1.0

    # Threshold: |z| > 3 is the standard 3-sigma anomaly boundary
    threshold = 3.0
    is_anomaly = bool(z_score > threshold)

    return {
        "is_anomaly": is_anomaly,
        "score": float(z_score),
        "method": "embedding_norm_zscore",
        "ratio": float(ratio),
        "current_mean": current_mean,
        "baseline_mean": baseline_mean,
    }
