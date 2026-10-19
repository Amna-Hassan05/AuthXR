#!/usr/bin/env python3
"""
Public Beat Saber subset (validate_subset_100users.csv) vs. your VR controller CSV

Kya karta hai:
  1. Public data se sirf wo columns nikalta hai jo tumhare data se compare ho sakte hain
     (Left/Right hand -> position + rotation stats, before/after cut windows)
  2. Tumhare controller CSV se same naam ke features banata hai (time windows se)
  3. Quality metrics compare karke report save karta hai

Usage:
  python compare_with_public.py validate_subset_100users.csv vr_controller_data.csv
  python compare_with_public.py validate_subset_100users.csv vr_controller_data.csv --win 1.0 --outdir out
"""

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

STATS = ["min", "max", "mean", "med", "std"]
POS_AX, ROT_AX = "xyz", "xyzw"
PUB_PAT = re.compile(r"^(b|a)(l|r)(p|r)(x|y|z|w)(min|max|mean|med|std)$")


# ---------- 1. Public data: sirf comparable columns ----------
def extract_public(df):
    cols = [c for c in df.columns if PUB_PAT.match(c)]
    return df[["uid"] + cols].copy()


# ---------- 2. Tumhara data: same naam ke features ----------
def build_my_features(path, win):
    d = pd.read_csv(path)
    out = {}
    t_all = d["time_sec"].to_numpy()
    anchors = np.arange(t_all.min() + win, t_all.max() - win, win)
    rows = []
    for t in anchors:
        row = {"anchor_time_sec": round(float(t), 3)}
        for hand, h in (("Left", "l"), ("Right", "r")):
            s = d[d["hand"] == hand]
            for wname, (lo, hi) in (("b", (t - win, t)), ("a", (t, t + win))):
                w = s[(s["time_sec"] >= lo) & (s["time_sec"] < hi)]
                if len(w) < 3:
                    continue
                for typ, axes, pre in (("p", POS_AX, "pos_"), ("r", ROT_AX, "rot_")):
                    for ax in axes:
                        v = w[pre + ax].to_numpy()
                        base = f"{wname}{h}{typ}{ax}"
                        row[base + "min"] = v.min()
                        row[base + "max"] = v.max()
                        row[base + "mean"] = v.mean()
                        row[base + "med"] = np.median(v)
                        row[base + "std"] = v.std()
        rows.append(row)
    return pd.DataFrame(rows).dropna(), d


# ---------- 3. Quality metrics ----------
def zscore(df):
    sd = df.std(ddof=0).replace(0, np.nan)
    return ((df - df.mean()) / sd).fillna(0.0)


def metrics(feat, kind):
    """kind = 'p' (position) ya 'r' (rotation)"""
    cols = [c for c in feat.columns if PUB_PAT.match(c) and c[2] == kind]
    X = feat[cols]
    Z = zscore(X)
    const = [c for c in cols if X[c].std() < 1e-3]
    skew = Z.skew().abs()
    kurt = Z.kurt()
    mean_cols = [c for c in cols if c.endswith("mean")]
    corr = np.mean([Z[c].corr(Z[c[:-4] + "med"]) for c in mean_cols if X[c].std() >= 1e-3 and X[c[:-4] + "med"].std() >= 1e-3] or [np.nan])
    inv = np.mean([(Z[c[:-3] + "min"] > Z[c[:-3] + "max"]).mean() for c in cols if c.endswith("min")])
    raw_inv = np.mean([(X[c[:-3] + "min"] > X[c[:-3] + "max"]).mean() for c in cols if c.endswith("min")])
    raw_negstd = np.mean([(X[c] < 0).mean() for c in cols if c.endswith("std")])
    return {
        "rows": len(X),
        "columns": len(cols),
        "constant_columns": len(const),
        "constant_columns_%": round(100 * len(const) / len(cols), 1),
        "raw_negative_std_%": round(100 * raw_negstd, 1),
        "raw_min>max_%": round(100 * raw_inv, 1),
        "mean_vs_median_corr": round(float(corr), 3),
        "avg_abs_skew": round(float(skew.mean()), 2),
        "avg_excess_kurtosis": round(float(kurt.mean()), 2),
        "outliers_|z|>3_%": round(100 * float((Z.abs() > 3).to_numpy().mean()), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("public_csv")
    ap.add_argument("my_csv")
    ap.add_argument("--win", type=float, default=1.0, help="window (sec) for before/after features")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    pub_raw = pd.read_csv(a.public_csv)
    pub = extract_public(pub_raw)
    mine, my_raw = build_my_features(a.my_csv, a.win)

    pub.to_csv(out / "public_hand_features.csv", index=False)
    mine.to_csv(out / "my_hand_features.csv", index=False)

    # raw-data sanity checks (sirf tumhare data pe possible)
    q = my_raw[["rot_x", "rot_y", "rot_z", "rot_w"]].to_numpy()
    qn = np.linalg.norm(q, axis=1)
    dt = my_raw[my_raw["hand"] == "Left"]["time_sec"].diff().dropna()
    extra = {
        "sampling_rate_Hz": round(1 / dt.median(), 1),
        "max_gap_sec": round(float(dt.max()), 2),
        "quaternion_norm_mean": round(float(qn.mean()), 4),
        "quaternion_norm_min": round(float(qn.min()), 4),
        "quaternion_norm_max": round(float(qn.max()), 4),
        "NaN_cells": int(my_raw.isna().sum().sum()),
        "duplicate_rows": int(my_raw.duplicated().sum()),
        "outlier_speed_rows(>10)": int((my_raw["speed"] > 10).sum()),
    }

    rep = []
    for kind, name in (("p", "HAND POSITION"), ("r", "HAND ROTATION")):
        rep.append(pd.DataFrame({"public": metrics(pub, kind), "mine": metrics(mine, kind)}).assign(group=name))
    rep = pd.concat(rep).reset_index().rename(columns={"index": "metric"})
    rep.to_csv(out / "comparison_report.csv", index=False)

    for name, g in rep.groupby("group", sort=False):
        print(f"\n=== {name} ===")
        print(g.drop(columns="group").to_string(index=False))
    print("\n=== YOUR RAW DATA CHECKS ===")
    for k, v in extra.items():
        print(f"{k:28s} {v}")
    print(f"\nSaved in: {out.resolve()}")


if __name__ == "__main__":
    main()
