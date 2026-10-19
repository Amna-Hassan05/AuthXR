# AuthXR Session Compare (POC)

Simple two-session movement comparison for your FYP demo.

## What it does

1. Loads two AuthXR CSVs (`session_1` / `session_2` or any files from `Data/`)
2. Cleans movement rows
3. Extracts basic features (speed, position, derived acceleration, rotation)
4. Computes **Similarity %** and **Difference %**
5. Shows bar chart, speed-over-time graphs, and a feature table in a web dashboard

## CSV columns used (from Unity logger)

```
timestamp_unix_ms, timestamp_unity, event_type, object_name, controller_name,
pos_x, pos_y, pos_z, rot_x, rot_y, rot_z, rot_w, speed_mps, interactor_name
```

Only `event_type == movement` rows are used for comparison.

## Setup (once)

Open PowerShell in the project folder:

```powershell
cd C:\Users\user\Desktop\MyVRProject
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r SessionCompare\requirements.txt
```

## Run the dashboard

```powershell
cd C:\Users\user\Desktop\MyVRProject
.\.venv\Scripts\Activate.ps1
streamlit run SessionCompare\app.py
```

Browser opens at `http://localhost:8501`.

## Demo flow

1. **Session 1 (you):** Play Unity → move controllers → stop Play  
   File appears in `Data/authxr_session_YYYYMMDD_HHMMSS.csv`
2. Optional rename/copy to `Data/session_1.csv`
3. **Session 2 (friend):** same steps → `session_2.csv` (or pick another `authxr_session_*.csv`)
4. In the dashboard: pick Session 1 + Session 2 → **COMPARE**
5. Show Similarity / Difference + charts for the FYP demo

## Notes

- Original CSVs are never modified.
- This is a POC: it shows whether two *sessions* look similar/different — it does **not** prove identity.
