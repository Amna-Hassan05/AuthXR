"""
AuthXR Session Compare — simple CSV cleaning, feature extraction, and comparison.
Used by the Streamlit dashboard (app.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Interpretation thresholds (configurable)
THRESHOLDS = {
    "very_similar": 80,
    "moderately_similar": 60,
    "noticeably_different": 40,
}

EXPECTED_COLUMNS = [
    "timestamp_unix_ms",
    "timestamp_unity",
    "event_type",
    "object_name",
    "controller_name",
    "pos_x",
    "pos_y",
    "pos_z",
    "rot_x",
    "rot_y",
    "rot_z",
    "rot_w",
    "speed_mps",
    "interactor_name",
]


def load_session_csv(path: str) -> pd.DataFrame:
    """Load a session CSV without modifying the file on disk."""
    df = pd.read_csv(path)
    return df


def clean_session(df: pd.DataFrame) -> pd.DataFrame:
    """
    Light cleaning for AuthXR movement CSVs.
    Does not write back to disk.
    """
    out = df.copy()

    # Keep only columns we know about (ignore extras if any)
    present = [c for c in EXPECTED_COLUMNS if c in out.columns]
    out = out[present]

    # Numeric columns
    numeric_cols = [
        c
        for c in [
            "timestamp_unix_ms",
            "timestamp_unity",
            "pos_x",
            "pos_y",
            "pos_z",
            "rot_x",
            "rot_y",
            "rot_z",
            "rot_w",
            "speed_mps",
        ]
        if c in out.columns
    ]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # Drop rows with missing critical fields
    required = [c for c in ["timestamp_unity", "event_type", "pos_x", "pos_y", "pos_z", "speed_mps"] if c in out.columns]
    out = out.dropna(subset=required)

    # Remove non-finite values
    for col in numeric_cols:
        out = out[np.isfinite(out[col])]

    # Movement rows only for comparison features / plots
    if "event_type" in out.columns:
        out = out[out["event_type"].astype(str).str.lower() == "movement"]

    # Sort + drop exact duplicate rows
    if "timestamp_unix_ms" in out.columns:
        out = out.sort_values("timestamp_unix_ms")
    out = out.drop_duplicates()

    # Invalid timestamps (non-positive unity time after start is ok; reject negatives)
    if "timestamp_unity" in out.columns:
        out = out[out["timestamp_unity"] >= 0]

    # Extreme outliers on speed (clip / drop obvious sensor glitches)
    if "speed_mps" in out.columns and len(out) > 10:
        # Drop speeds above a hard physical ceiling for handheld VR (~15 m/s)
        out = out[out["speed_mps"].abs() <= 15.0]
        # Soft IQR-style filter on position jumps is optional; keep simple
        q99 = out["speed_mps"].quantile(0.99)
        out = out[out["speed_mps"] <= max(q99 * 3.0, 0.01)]

    # Extreme position outliers relative to session median
    for axis in ("pos_x", "pos_y", "pos_z"):
        if axis not in out.columns or len(out) < 20:
            continue
        med = out[axis].median()
        mad = (out[axis] - med).abs().median()
        if mad < 1e-6:
            continue
        # Keep within ~20 median absolute deviations (very loose)
        out = out[(out[axis] - med).abs() <= mad * 20.0]

    out = out.reset_index(drop=True)
    return out


def _quat_to_euler_deg(qx, qy, qz, qw) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Quaternion (x,y,z,w) → Euler degrees (roll, pitch, yaw). Simple POC conversion."""
    # roll (x)
    sinr_cosp = 2.0 * (qw * qx + qy * qz)
    cosr_cosp = 1.0 - 2.0 * (qx * qx + qy * qy)
    roll = np.degrees(np.arctan2(sinr_cosp, cosr_cosp))

    # pitch (y)
    sinp = 2.0 * (qw * qy - qz * qx)
    sinp = np.clip(sinp, -1.0, 1.0)
    pitch = np.degrees(np.arcsin(sinp))

    # yaw (z)
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    yaw = np.degrees(np.arctan2(siny_cosp, cosy_cosp))

    return roll, pitch, yaw


def extract_features(df: pd.DataFrame) -> Dict[str, float]:
    """
    Extract basic movement features from cleaned AuthXR movement rows.
    Only uses columns that exist in the CSV.
    """
    feats: Dict[str, float] = {}
    if df is None or len(df) == 0:
        return feats

    # Prefer one controller for a cleaner signature (Right if present, else Left, else all)
    work = df
    if "controller_name" in df.columns:
        names = df["controller_name"].astype(str)
        if names.str.contains("Right", case=False, na=False).any():
            work = df[names.str.contains("Right", case=False, na=False)].copy()
        elif names.str.contains("Left", case=False, na=False).any():
            work = df[names.str.contains("Left", case=False, na=False)].copy()

    if len(work) == 0:
        work = df

    # --- Position ---
    if all(c in work.columns for c in ("pos_x", "pos_y", "pos_z")):
        for axis in ("x", "y", "z"):
            col = f"pos_{axis}"
            feats[f"mean_pos_{axis}"] = float(work[col].mean())
            feats[f"std_pos_{axis}"] = float(work[col].std(ddof=0))
            feats[f"range_pos_{axis}"] = float(work[col].max() - work[col].min())

        # Path length (total distance traveled)
        dpos = work[["pos_x", "pos_y", "pos_z"]].diff().dropna()
        step = np.linalg.norm(dpos.values, axis=1)
        feats["path_length_m"] = float(step.sum())

        # Overall movement magnitude: mean distance from session centroid
        centroid = work[["pos_x", "pos_y", "pos_z"]].mean().values
        dist = np.linalg.norm(work[["pos_x", "pos_y", "pos_z"]].values - centroid, axis=1)
        feats["mean_distance_from_centroid_m"] = float(dist.mean())
        feats["std_distance_from_centroid_m"] = float(dist.std(ddof=0))

    # --- Speed (already logged as speed_mps) ---
    if "speed_mps" in work.columns:
        spd = work["speed_mps"].astype(float)
        feats["mean_speed_mps"] = float(spd.mean())
        feats["max_speed_mps"] = float(spd.max())
        feats["std_speed_mps"] = float(spd.std(ddof=0))

        # Derived acceleration from speed over time
        if "timestamp_unity" in work.columns and len(work) > 2:
            t = work["timestamp_unity"].astype(float).values
            s = spd.values
            dt = np.diff(t)
            ds = np.diff(s)
            valid = dt > 1e-4
            if valid.any():
                accel = np.abs(ds[valid] / dt[valid])
                # Cap absurd spikes
                accel = accel[accel <= 50.0]
                if len(accel) > 0:
                    feats["mean_accel_mps2"] = float(accel.mean())
                    feats["max_accel_mps2"] = float(accel.max())
                    feats["std_accel_mps2"] = float(accel.std(ddof=0))

    # --- Rotation (quaternion → euler stats) ---
    if all(c in work.columns for c in ("rot_x", "rot_y", "rot_z", "rot_w")):
        roll, pitch, yaw = _quat_to_euler_deg(
            work["rot_x"].values,
            work["rot_y"].values,
            work["rot_z"].values,
            work["rot_w"].values,
        )
        for name, arr in (("roll", roll), ("pitch", pitch), ("yaw", yaw)):
            feats[f"mean_rot_{name}_deg"] = float(np.mean(arr))
            feats[f"std_rot_{name}_deg"] = float(np.std(arr))
            feats[f"range_rot_{name}_deg"] = float(np.max(arr) - np.min(arr))

        # Angular change magnitude between consecutive samples (degrees)
        # Using quaternion relative angle: 2*acos(|dot|)
        q = work[["rot_x", "rot_y", "rot_z", "rot_w"]].astype(float).values
        # Normalize
        norms = np.linalg.norm(q, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        q = q / norms
        if len(q) > 1:
            dots = np.abs(np.sum(q[1:] * q[:-1], axis=1))
            dots = np.clip(dots, 0.0, 1.0)
            ang = np.degrees(2.0 * np.arccos(dots))
            feats["mean_angular_change_deg"] = float(ang.mean())
            feats["std_angular_change_deg"] = float(ang.std(ddof=0))

    # Session duration helper (not used in distance if zero variance, but useful in UI)
    if "timestamp_unity" in work.columns and len(work) > 1:
        feats["duration_s"] = float(work["timestamp_unity"].max() - work["timestamp_unity"].min())
        feats["sample_count"] = float(len(work))

    # Replace NaN/inf in features with 0
    cleaned = {}
    for k, v in feats.items():
        if v is None or not np.isfinite(v):
            cleaned[k] = 0.0
        else:
            cleaned[k] = float(v)
    return cleaned


def normalize_feature_pair(v1: float, v2: float) -> Tuple[float, float]:
    """Scale a feature pair into roughly comparable units using max-abs normalization."""
    scale = max(abs(v1), abs(v2), 1e-8)
    return v1 / scale, v2 / scale


@dataclass
class CompareResult:
    similarity: float
    difference: float
    interpretation: str
    features_s1: Dict[str, float]
    features_s2: Dict[str, float]
    feature_rows: List[Dict[str, float]]
    shared_feature_names: List[str]


def interpret_similarity(similarity: float, thresholds: Dict[str, int] | None = None) -> str:
    t = thresholds or THRESHOLDS
    if similarity >= t["very_similar"]:
        return "Very similar movement patterns"
    if similarity >= t["moderately_similar"]:
        return "Moderately similar movement patterns"
    if similarity >= t["noticeably_different"]:
        return "Noticeably different movement patterns"
    return "Very different movement patterns"


def compare_sessions(
    features_s1: Dict[str, float],
    features_s2: Dict[str, float],
    thresholds: Dict[str, int] | None = None,
) -> CompareResult:
    """
    Compare two feature dicts with normalized Euclidean distance → similarity 0–100.

    For each shared feature:
      n1, n2 = value / max(|v1|, |v2|, eps)
    distance = sqrt(mean((n1-n2)^2))
    similarity = 100 * (1 - clamp(distance, 0, 1))
    """
    # Exclude meta counts from distance (still show in table if desired)
    skip = {"sample_count", "duration_s"}
    names = sorted(set(features_s1.keys()) & set(features_s2.keys()) - skip)
    if not names:
        return CompareResult(
            similarity=0.0,
            difference=100.0,
            interpretation="Not enough comparable features",
            features_s1=features_s1,
            features_s2=features_s2,
            feature_rows=[],
            shared_feature_names=[],
        )

    diffs_sq = []
    rows = []
    for name in names:
        v1 = float(features_s1[name])
        v2 = float(features_s2[name])
        n1, n2 = normalize_feature_pair(v1, v2)
        diffs_sq.append((n1 - n2) ** 2)
        rows.append(
            {
                "feature": name,
                "session_1": v1,
                "session_2": v2,
                "abs_difference": abs(v1 - v2),
                "relative_difference": abs(n1 - n2),
            }
        )

    distance = float(np.sqrt(np.mean(diffs_sq)))
    distance = min(max(distance, 0.0), 1.0)
    similarity = 100.0 * (1.0 - distance)
    difference = 100.0 - similarity

    return CompareResult(
        similarity=round(similarity, 1),
        difference=round(difference, 1),
        interpretation=interpret_similarity(similarity, thresholds),
        features_s1=features_s1,
        features_s2=features_s2,
        feature_rows=rows,
        shared_feature_names=names,
    )


def movement_series(df: pd.DataFrame, max_points: int = 800) -> pd.DataFrame:
    """
    Build a downsampled movement magnitude series for plotting.
    Magnitude = speed_mps if present, else frame-to-frame position delta.
    Time axis = timestamp_unity (seconds from session start), re-based to 0.
    """
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["t", "signal"])

    work = df.copy()
    if "controller_name" in work.columns:
        names = work["controller_name"].astype(str)
        if names.str.contains("Right", case=False, na=False).any():
            work = work[names.str.contains("Right", case=False, na=False)]

    if "timestamp_unity" not in work.columns:
        work = work.reset_index(drop=True)
        t = np.arange(len(work), dtype=float)
    else:
        t = work["timestamp_unity"].astype(float).values
        t = t - t.min()

    if "speed_mps" in work.columns:
        signal = work["speed_mps"].astype(float).values
    elif all(c in work.columns for c in ("pos_x", "pos_y", "pos_z")):
        d = work[["pos_x", "pos_y", "pos_z"]].diff().fillna(0.0).values
        signal = np.linalg.norm(d, axis=1)
    else:
        signal = np.zeros(len(work))

    series = pd.DataFrame({"t": t, "signal": signal})
    if len(series) > max_points:
        idx = np.linspace(0, len(series) - 1, max_points).astype(int)
        series = series.iloc[idx].reset_index(drop=True)
    return series
