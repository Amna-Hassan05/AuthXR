#!/usr/bin/env python3
"""
VRInteractionLogger log filter -> CSV

Usage examples:
  python filter_vr_logs.py odh_logs.txt
  python filter_vr_logs.py odh_logs.txt -o out.csv
  python filter_vr_logs.py odh_logs.txt --hand Left
  python filter_vr_logs.py odh_logs.txt --event movement --tmin 10 --tmax 60
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# Sirf [VRInteractionLogger] wali lines uthao (stack trace / system lines ignore)
LINE_RE = re.compile(r"^(?P<clock>\d{2}:\d{2}:\d{2}\.\d+)\s+.*?\[VRInteractionLogger\]\s+(?P<data>.+)$")

HEADER = [
    "clock_time",      # logcat time (HH:MM:SS.mmm)
    "timestamp_ms",    # unix epoch ms
    "time_sec",        # app time in seconds
    "event",           # e.g. movement
    "object_name",     # e.g. Left Controller
    "object_id",       # e.g. LeftController
    "pos_x", "pos_y", "pos_z",
    "rot_x", "rot_y", "rot_z", "rot_w",
    "speed",           # last column (approx speed, m/s)
]
# Extra columns jo script khud add karti hai:
OUT_HEADER = ["hand", "device", "is_moving"] + HEADER


def parse_log(path):
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_RE.match(line.strip())
            if not m:
                continue
            parts = m.group("data").rstrip(",").split(",")
            if len(parts) != len(HEADER) - 1:  # malformed row skip
                continue
            rows.append([m.group("clock")] + [p.strip() for p in parts])
    return rows


def main():
    ap = argparse.ArgumentParser(description="Filter VRInteractionLogger logs into CSV")
    ap.add_argument("input", help="Log .txt file")
    ap.add_argument("-o", "--output", help="Output CSV (default: <input>_filtered.csv)")
    ap.add_argument("--event", help="Event type filter, e.g. movement")
    ap.add_argument("--object", dest="obj", help="object_id filter, e.g. LeftController / RightController")
    ap.add_argument("--tmin", type=float, help="Min time_sec")
    ap.add_argument("--tmax", type=float, help="Max time_sec")
    ap.add_argument("--hand", choices=["Left", "Right"], help="Sirf Left ya Right controller")
    ap.add_argument("--move-thresh", type=float, default=0.01,
                    help="speed > is value => is_moving=1 (default 0.01)")
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        sys.exit(f"File nahi mili: {inp}")
    out = Path(args.output) if args.output else inp.with_name(inp.stem + "_filtered.csv")

    rows = parse_log(inp)
    total = len(rows)
    idx = {h: i for i, h in enumerate(HEADER)}

    def keep(r):
        if args.event and r[idx["event"]] != args.event:
            return False
        if args.obj and r[idx["object_id"]] != args.obj:
            return False
        t = float(r[idx["time_sec"]])
        if args.tmin is not None and t < args.tmin:
            return False
        if args.tmax is not None and t > args.tmax:
            return False
        return True

    rows = [r for r in rows if keep(r)]

    def hand_of(r):
        oid = r[idx["object_id"]].lower()
        return "Left" if "left" in oid else "Right" if "right" in oid else "Unknown"

    def device_of(r):
        oid = r[idx["object_id"]].lower()
        return "Controller" if "controller" in oid else "Hand" if "hand" in oid else "Head" if "head" in oid else "Unknown"

    if args.hand:
        rows = [r for r in rows if hand_of(r) == args.hand]
    rows = [[hand_of(r), device_of(r), 1 if float(r[idx["speed"]]) > args.move_thresh else 0] + r for r in rows]

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(OUT_HEADER)
        w.writerows(rows)

    print(f"Parsed: {total} rows | Saved: {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()