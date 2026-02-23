"""
Neykuri v1 — Database Viewer (Fixed)
- Cards rendered without st.columns HTML bug
- Timestamps shown in IST (Indian Standard Time, UTC+5:30)
- Images displayed using st.image() — no base64 HTML rendering issues

Run from backend/ directory:
    streamlit run db_viewer.py --server.port 8502
"""

import sqlite3
import os
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
from PIL import Image

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "neykuri_database.db")
IST_OFFSET = timedelta(hours=5, minutes=30)

DOSHA_COLORS = {
    "Kabam":         "#38BDF8",
    "Pithakabam":    "#A78BFA",
    "Pithalipitham": "#FBBF24",
    "Pitham":        "#F87171",
    "Pithavatham":   "#34D399",
}
DOSHA_ICONS = {
    "Kabam":         "💧",
    "Pithakabam":    "🌀",
    "Pithalipitham": "🔥",
    "Pitham":        "⚡",
    "Pithavatham":   "🌿",
}

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & CSS
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Neykuri · DB Viewer",
    page_icon="🗄️",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

:root {
    --bg:     #080C14;
    --panel:  #0E1420;
    --card:   #141B2D;
    --border: #1E2A40;
    --text:   #E2E8F0;
    --muted:  #64748B;
    --accent: #38BDF8;
}
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Mono', monospace !important;
}
[data-testid="stSidebar"] {
    background: var(--panel) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stHeader"] { background: transparent !important; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; }

[data-testid="stMetric"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.68rem !important; color: var(--muted) !important;
    text-transform: uppercase; letter-spacing: 0.1em;
}
[data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important; color: var(--text) !important;
}
.stButton > button {
    background: var(--accent) !important; color: #080C14 !important;
    font-family: 'Syne', sans-serif !important; font-weight: 700 !important;
    border: none !important; border-radius: 6px !important;
}
/* Image border fix */
[data-testid="stImage"] img {
    border-radius: 8px 8px 0 0 !important;
    width: 100% !important;
    object-fit: cover !important;
    height: 160px !important;
}
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
.section-title {
    font-family: 'Syne', sans-serif; font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted);
    border-bottom: 1px solid var(--border); padding-bottom: 0.4rem;
    margin: 1.2rem 0 0.7rem;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def to_ist(timestamp_str: str) -> str:
    """
    Convert stored UTC timestamp string to IST formatted string.
    Input format : 20260220_181858_624074  (YYYYMMDD_HHMMSS_ffffff)
    Output format: 20 Feb 2026, 11:48 PM IST
    """
    try:
        dt_utc = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S_%f")
        dt_ist = dt_utc + IST_OFFSET
        return dt_ist.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return timestamp_str


def load_records() -> list:
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM patient_records ORDER BY record_id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_image(path: str):
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:0.8rem;">
        <span style="font-size:1.6rem;">🗄️</span>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;
                        color:#E2E8F0;">DB Viewer</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.62rem;
                        color:#38BDF8;letter-spacing:0.1em;">NEYKURI · RECORDS</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    all_records = load_records()

    st.markdown('<div class="section-title">Filters</div>', unsafe_allow_html=True)
    patient_ids     = ["All"] + sorted(set(r["patient_id"] for r in all_records))
    selected_patient = st.selectbox("Patient ID", patient_ids)

    dosha_options   = ["All"] + list(DOSHA_COLORS.keys())
    selected_dosha  = st.selectbox("Dosha Class", dosha_options)

    st.markdown('<div class="section-title">View Mode</div>', unsafe_allow_html=True)
    view_mode = st.radio(
        "mode", ["🖼️ Cards with Images", "📊 Table View", "📈 Charts"],
        label_visibility="collapsed",
    )

    st.button("🔄 Refresh", use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# APPLY FILTERS
# ─────────────────────────────────────────────────────────────────────────────
records = all_records
if selected_patient != "All":
    records = [r for r in records if r["patient_id"] == selected_patient]
if selected_dosha != "All":
    records = [r for r in records if r["prediction"] == selected_dosha]

# ─────────────────────────────────────────────────────────────────────────────
# HEADER + METRICS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## Patient Records Database")
st.caption("Live view of neykuri_database.db · Timestamps shown in IST (UTC+5:30)")

if all_records:
    df_all = pd.DataFrame(all_records)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Records",   len(df_all))
    c2.metric("Unique Patients", df_all["patient_id"].nunique())
    c3.metric("Top Dosha",       df_all["prediction"].value_counts().idxmax())
    c4.metric("Avg Confidence",  str(round(df_all["confidence"].mean() * 100, 1)) + "%")

st.markdown(
    f'<div class="section-title">Showing {len(records)} record(s)</div>',
    unsafe_allow_html=True,
)

if not records:
    st.info("No records match your filters. Submit images via the main app first.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 1 — CARDS WITH IMAGES  (fixed: using st.image + st.markdown separately)
# ══════════════════════════════════════════════════════════════════════════════
if view_mode == "🖼️ Cards with Images":

    COLS = 3
    rows = [records[i:i+COLS] for i in range(0, len(records), COLS)]

    for row in rows:
        cols = st.columns(COLS, gap="medium")
        for col, rec in zip(cols, row):
            color = DOSHA_COLORS.get(rec["prediction"], "#64748B")
            icon  = DOSHA_ICONS.get(rec["prediction"],  "◎")
            conf  = round(rec["confidence"] * 100, 2)
            ist   = to_ist(rec["timestamp"])

            with col:
                # Coloured top border via container
                st.markdown(
                    f'<div style="border:1px solid {color};border-radius:12px;'
                    f'overflow:hidden;background:#141B2D;margin-bottom:4px;">',
                    unsafe_allow_html=True,
                )

                # ── Image ────────────────────────────────────────────────
                img = load_image(rec["image_path"])
                if img:
                    st.image(img, use_container_width=True)
                else:
                    st.markdown(
                        '<div style="height:140px;background:#0E1420;'
                        'display:flex;align-items:center;justify-content:center;">'
                        '<span style="font-size:2rem;opacity:0.2;">🧫</span></div>',
                        unsafe_allow_html=True,
                    )

                # ── Info block ────────────────────────────────────────────
                st.markdown(f"""
                <div style="padding:0.8rem 1rem;">
                    <div style="display:flex;justify-content:space-between;
                                align-items:center;margin-bottom:6px;">
                        <span style="font-family:'Syne',sans-serif;font-weight:800;
                                     font-size:1rem;color:{color};">
                            {icon} {rec['prediction']}
                        </span>
                        <span style="font-family:'DM Mono',monospace;font-size:0.65rem;
                                     color:#64748B;">#{rec['record_id']}</span>
                    </div>
                    <div style="font-family:'DM Mono',monospace;font-size:0.72rem;
                                color:#94A3B8;line-height:1.9;">
                        <div>👤 &nbsp;{rec['patient_id']}</div>
                        <div>🕐 &nbsp;{ist}</div>
                    </div>
                    <div style="margin-top:10px;">
                        <div style="display:flex;justify-content:space-between;
                                    font-family:'DM Mono',monospace;font-size:0.68rem;
                                    color:#94A3B8;margin-bottom:4px;">
                            <span>Confidence</span>
                            <span style="color:{color};font-weight:600;">{conf}%</span>
                        </div>
                        <div style="background:#1E2A40;border-radius:99px;
                                    height:6px;overflow:hidden;">
                            <div style="width:{conf}%;height:100%;
                                        background:{color};border-radius:99px;"></div>
                        </div>
                    </div>
                </div>
                </div>
                """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 2 — TABLE VIEW
# ══════════════════════════════════════════════════════════════════════════════
elif view_mode == "📊 Table View":

    # ── Thumbnail strip ───────────────────────────────────────────────────
    st.markdown('<div class="section-title">Image Thumbnails</div>',
                unsafe_allow_html=True)

    visible = records[:9]
    thumb_cols = st.columns(len(visible), gap="small")
    for col, rec in zip(thumb_cols, visible):
        color = DOSHA_COLORS.get(rec["prediction"], "#64748B")
        img   = load_image(rec["image_path"])
        with col:
            if img:
                st.image(img, use_container_width=True)
            st.markdown(
                f'<div style="text-align:center;font-family:\'DM Mono\',monospace;'
                f'font-size:0.6rem;color:{color};margin-top:2px;">'
                f'#{rec["record_id"]} · {rec["prediction"][:4]}</div>',
                unsafe_allow_html=True,
            )

    # ── Full table ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">All Records</div>',
                unsafe_allow_html=True)

    rows_display = []
    for rec in records:
        rows_display.append({
            "ID":           rec["record_id"],
            "Patient ID":   rec["patient_id"],
            "Dosha":        DOSHA_ICONS.get(rec["prediction"], "") + " " + rec["prediction"],
            "Confidence %": round(rec["confidence"] * 100, 2),
            "Date & Time (IST)": to_ist(rec["timestamp"]),
            "Image Path":   rec["image_path"],
        })

    df = pd.DataFrame(rows_display)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Confidence %": st.column_config.ProgressColumn(
                "Confidence %",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
            "ID": st.column_config.NumberColumn("ID", width="small"),
        },
    )

    # Download CSV
    csv = df.to_csv(index=False)
    st.download_button(
        label="⬇️ Download as CSV",
        data=csv,
        file_name="neykuri_records.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 3 — CHARTS
# ══════════════════════════════════════════════════════════════════════════════
elif view_mode == "📈 Charts":

    df = pd.DataFrame(records)
    df["conf_pct"] = df["confidence"] * 100
    df["ist_time"] = df["timestamp"].apply(to_ist)

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown('<div class="section-title">Dosha Distribution</div>',
                    unsafe_allow_html=True)
        dist = df["prediction"].value_counts().rename_axis("Dosha").reset_index(name="Count")
        st.bar_chart(dist.set_index("Dosha"), use_container_width=True, height=220)

    with c2:
        st.markdown('<div class="section-title">Confidence per Record</div>',
                    unsafe_allow_html=True)
        conf_chart = df[["record_id", "conf_pct"]].set_index("record_id")
        st.bar_chart(
            conf_chart.rename(columns={"conf_pct": "Confidence %"}),
            use_container_width=True, height=220,
        )

    st.markdown('<div class="section-title">Confidence Trend Over Time</div>',
                unsafe_allow_html=True)
    trend = df[["record_id", "conf_pct"]].set_index("record_id").sort_index()
    st.line_chart(
        trend.rename(columns={"conf_pct": "Confidence %"}),
        use_container_width=True, height=200,
    )

    st.markdown('<div class="section-title">Records per Patient</div>',
                unsafe_allow_html=True)
    per_pt = df["patient_id"].value_counts().rename_axis("Patient").reset_index(name="Records")
    st.bar_chart(per_pt.set_index("Patient"), use_container_width=True, height=180)