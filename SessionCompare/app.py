"""
AuthXR Movement Comparison Dashboard (Streamlit)

Run from project root:
  pip install -r SessionCompare/requirements.txt
  streamlit run SessionCompare/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compare_core import (  # noqa: E402
    THRESHOLDS,
    clean_session,
    compare_sessions,
    extract_features,
    load_session_csv,
    movement_series,
)

PROJECT_DATA = ROOT.parent / "Data"

st.set_page_config(
    page_title="AuthXR Movement Comparison",
    page_icon=None,
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      .result-card {
        border: 1px solid #d0d7de;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        background: #f6f8fa;
      }
      .metric-big { font-size: 2.4rem; font-weight: 700; margin: 0; }
      .muted { color: #57606a; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AuthXR Movement Comparison")
st.caption(
    "POC: compare two recorded VR controller sessions and show how similar or different "
    "their movement patterns are. Not an identity claim — only a session-to-session comparison."
)

# --- Sidebar thresholds ---
with st.sidebar:
    st.header("Interpretation thresholds")
    t_very = st.slider("Very similar ≥", 50, 100, THRESHOLDS["very_similar"])
    t_mod = st.slider("Moderately similar ≥", 30, t_very - 1, THRESHOLDS["moderately_similar"])
    t_notice = st.slider("Noticeably different ≥", 0, t_mod - 1, THRESHOLDS["noticeably_different"])
    thresholds = {
        "very_similar": t_very,
        "moderately_similar": t_mod,
        "noticeably_different": t_notice,
    }
    st.markdown("---")
    st.markdown("**Data folder**")
    st.code(str(PROJECT_DATA), language=None)


def _file_options() -> list[Path]:
    if not PROJECT_DATA.exists():
        return []
    return sorted(PROJECT_DATA.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)


options = _file_options()
option_labels = [p.name for p in options]

col1, col2 = st.columns(2)
with col1:
    st.subheader("Session 1")
    label_s1 = st.text_input("Label", value="Me", key="label_s1")
    src_s1 = st.radio("Source", ["From Data folder", "Upload CSV"], key="src_s1", horizontal=True)
    file_s1 = None
    path_s1 = None
    if src_s1 == "From Data folder":
        pick = st.selectbox("CSV", option_labels, key="pick_s1", index=0 if option_labels else None)
        if pick:
            path_s1 = PROJECT_DATA / pick
    else:
        file_s1 = st.file_uploader("Upload session_1.csv", type=["csv"], key="up_s1")

with col2:
    st.subheader("Session 2")
    label_s2 = st.text_input("Label", value="Friend", key="label_s2")
    src_s2 = st.radio("Source", ["From Data folder", "Upload CSV"], key="src_s2", horizontal=True)
    file_s2 = None
    path_s2 = None
    if src_s2 == "From Data folder":
        default_idx = 1 if len(option_labels) > 1 else (0 if option_labels else None)
        pick = st.selectbox("CSV", option_labels, key="pick_s2", index=default_idx)
        if pick:
            path_s2 = PROJECT_DATA / pick
    else:
        file_s2 = st.file_uploader("Upload session_2.csv", type=["csv"], key="up_s2")

st.markdown("")
compare_clicked = st.button("COMPARE", type="primary", use_container_width=False)


def _read_input(uploaded, path: Path | None) -> pd.DataFrame | None:
    if uploaded is not None:
        return pd.read_csv(uploaded)
    if path is not None and path.exists():
        return load_session_csv(str(path))
    return None


if compare_clicked:
    raw1 = _read_input(file_s1, path_s1)
    raw2 = _read_input(file_s2, path_s2)

    if raw1 is None or raw2 is None:
        st.error("Please select or upload both Session 1 and Session 2 CSV files.")
        st.stop()

    if path_s1 and path_s2 and path_s1.resolve() == path_s2.resolve() and file_s1 is None and file_s2 is None:
        st.warning("You selected the same file for both sessions. Comparison will still run, but similarity may be very high.")

    with st.spinner("Cleaning and comparing sessions..."):
        clean1 = clean_session(raw1)
        clean2 = clean_session(raw2)
        feats1 = extract_features(clean1)
        feats2 = extract_features(clean2)
        result = compare_sessions(feats1, feats2, thresholds=thresholds)

    if len(clean1) < 10 or len(clean2) < 10:
        st.error(
            f"Not enough movement rows after cleaning "
            f"(Session 1: {len(clean1)}, Session 2: {len(clean2)}). "
            "Record longer sessions with controller movement."
        )
        st.stop()

    st.markdown("---")
    st.subheader("Overall comparison")

    st.markdown(
        f"""
        <div class="result-card">
          <p class="muted" style="margin:0 0 0.5rem 0;">MOVEMENT COMPARISON</p>
          <p><strong>Session 1:</strong> {label_s1}<br/>
             <strong>Session 2:</strong> {label_s2}</p>
          <p class="metric-big">Similarity: {result.similarity:.1f}%</p>
          <p class="metric-big" style="font-size:1.6rem;">Difference: {result.difference:.1f}%</p>
          <p style="margin:0.75rem 0 0 0; font-size:1.15rem;"><strong>{result.interpretation}</strong></p>
          <p class="muted" style="margin:0.5rem 0 0 0;">
            The movement patterns are {result.difference:.1f}% different (POC session comparison — not an identity verdict).
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Feature bar chart ---
    st.markdown("---")
    st.subheader("Feature comparison")

    # Pick a readable subset of important features for the bar chart
    preferred = [
        "mean_speed_mps",
        "std_speed_mps",
        "max_speed_mps",
        "mean_accel_mps2",
        "std_accel_mps2",
        "path_length_m",
        "mean_distance_from_centroid_m",
        "std_pos_x",
        "std_pos_y",
        "std_pos_z",
        "mean_angular_change_deg",
        "std_angular_change_deg",
        "std_rot_yaw_deg",
        "std_rot_pitch_deg",
        "std_rot_roll_deg",
    ]
    chart_names = [n for n in preferred if n in result.shared_feature_names]
    if not chart_names:
        chart_names = result.shared_feature_names[:12]

    bar_rows = []
    for name in chart_names:
        bar_rows.append({"feature": name, "value": result.features_s1[name], "session": label_s1})
        bar_rows.append({"feature": name, "value": result.features_s2[name], "session": label_s2})
    bar_df = pd.DataFrame(bar_rows)

    fig_bar = px.bar(
        bar_df,
        x="feature",
        y="value",
        color="session",
        barmode="group",
        title="Extracted movement features (Session 1 vs Session 2)",
        labels={"feature": "Feature", "value": "Value", "session": "Session"},
    )
    fig_bar.update_layout(xaxis_tickangle=-35, height=420, legend_title_text="")
    st.plotly_chart(fig_bar, use_container_width=True)

    # --- Movement over time ---
    st.markdown("---")
    st.subheader("Movement data comparison")
    st.caption("Signal: controller speed (m/s) over session time. Sessions may differ in length.")

    s1 = movement_series(clean1)
    s2 = movement_series(clean2)

    c_a, c_b = st.columns(2)
    with c_a:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=s1["t"], y=s1["signal"], mode="lines", name=label_s1, line=dict(width=1.5)))
        fig1.update_layout(
            title=f"{label_s1} — speed over time",
            xaxis_title="Time (s)",
            yaxis_title="Speed (m/s)",
            height=320,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        st.plotly_chart(fig1, use_container_width=True)
        st.caption(f"Samples used: {len(clean1)} movement rows · duration ≈ {feats1.get('duration_s', 0):.1f}s")

    with c_b:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=s2["t"], y=s2["signal"], mode="lines", name=label_s2, line=dict(width=1.5, color="#c44e52")))
        fig2.update_layout(
            title=f"{label_s2} — speed over time",
            xaxis_title="Time (s)",
            yaxis_title="Speed (m/s)",
            height=320,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(f"Samples used: {len(clean2)} movement rows · duration ≈ {feats2.get('duration_s', 0):.1f}s")

    # Overlay (normalized time 0–1) for fair visual compare when lengths differ
    with st.expander("Overlay both sessions (time normalized 0–1)"):
        def _norm_time(series: pd.DataFrame) -> pd.DataFrame:
            out = series.copy()
            tmax = float(out["t"].max()) if len(out) else 1.0
            out["t_norm"] = out["t"] / tmax if tmax > 0 else out["t"]
            return out

        n1 = _norm_time(s1)
        n2 = _norm_time(s2)
        fig_o = go.Figure()
        fig_o.add_trace(go.Scatter(x=n1["t_norm"], y=n1["signal"], mode="lines", name=label_s1))
        fig_o.add_trace(go.Scatter(x=n2["t_norm"], y=n2["signal"], mode="lines", name=label_s2))
        fig_o.update_layout(
            title="Speed over normalized session time",
            xaxis_title="Normalized time (0 = start, 1 = end)",
            yaxis_title="Speed (m/s)",
            height=360,
        )
        st.plotly_chart(fig_o, use_container_width=True)

    # --- Feature details table ---
    st.markdown("---")
    st.subheader("Feature details")
    table = pd.DataFrame(result.feature_rows)
    if len(table):
        table = table.rename(
            columns={
                "feature": "Feature",
                "session_1": f"Session 1 ({label_s1})",
                "session_2": f"Session 2 ({label_s2})",
                "abs_difference": "Difference",
                "relative_difference": "Relative diff (0–1)",
            }
        )
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.info("No shared features to display.")

else:
    st.info(
        "Select two session CSVs (e.g. from the project `Data/` folder), then click **COMPARE**.\n\n"
        "Tip for demos: record yourself → copy/rename file to `session_1.csv`, "
        "then record your friend → `session_2.csv`."
    )
