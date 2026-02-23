"""
Neykuri v1 — Siddha Diagnostic Frontend (Redesigned)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL: Zero TensorFlow / Keras imports.
All HTML rendering moved to safe zones only (never inside st.columns).
Timestamps shown in IST (UTC+5:30).
"""

import json
from datetime import datetime, timedelta

import streamlit as st
import requests
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
API_BASE   = "http://127.0.0.1:8000"
IST_OFFSET = timedelta(hours=5, minutes=30)

DOSHA_META = {
    "Kabam":         {"color": "#38BDF8", "icon": "💧", "bg": "#38BDF808",
                      "desc": "Kapha-dominant. Heaviness, congestion, and fluid retention signals."},
    "Pithakabam":    {"color": "#A78BFA", "icon": "🌀", "bg": "#A78BFA08",
                      "desc": "Pitta-Kapha mixed. Inflammatory tendency with mucosal congestion."},
    "Pithalipitham": {"color": "#FBBF24", "icon": "🔥", "bg": "#FBBF2408",
                      "desc": "Pitta-Lipid imbalance. Metabolic heat with fat-metabolism disruption."},
    "Pitham":        {"color": "#F87171", "icon": "⚡", "bg": "#F8717108",
                      "desc": "Pitta-dominant. Acute heat, sharp inflammatory and digestive activity."},
    "Pithavatham":   {"color": "#34D399", "icon": "🌿", "bg": "#34D39908",
                      "desc": "Pitta-Vata mixed. Dryness, volatility, and erratic inflammatory patterns."},
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def to_ist(timestamp_str: str) -> str:
    try:
        dt_utc = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S_%f")
        dt_ist = dt_utc + IST_OFFSET
        return dt_ist.strftime("%d %b %Y  %I:%M %p IST")
    except Exception:
        return timestamp_str


def backend_health() -> dict:
    try:
        return requests.get(f"{API_BASE}/health", timeout=4).json()
    except Exception:
        return {"status": "unreachable", "model_loaded": False}


def call_analyze(patient_id, image_bytes, filename) -> dict:
    r = requests.post(
        f"{API_BASE}/analyze",
        data={"patient_id": patient_id},
        files={"file": (filename, image_bytes, "image/jpeg")},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def call_history(patient_id) -> dict:
    r = requests.get(f"{API_BASE}/history/{patient_id}", timeout=10)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Neykuri · Siddha Diagnostics",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS  — only safe top-level styles, no layout HTML in columns
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

:root {
    --bg:      #080C14;
    --panel:   #0E1420;
    --card:    #141B2D;
    --border:  #1E2A40;
    --text:    #E2E8F0;
    --muted:   #64748B;
    --accent:  #38BDF8;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Mono', monospace !important;
}
[data-testid="stSidebar"] {
    background: var(--panel) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stHeader"]      { background: transparent !important; }
[data-testid="stBottom"]      { background: var(--bg) !important; }

h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    letter-spacing: -0.02em !important;
}

/* ── Inputs ── */
.stTextInput input {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-family: 'DM Mono', monospace !important;
    border-radius: 8px !important;
}
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px #38BDF820 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: var(--accent) !important;
    color: #080C14 !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.2rem !important;
    transition: opacity .15s, transform .1s !important;
}
.stButton > button:hover  { opacity:.85 !important; transform:translateY(-1px) !important; }
.stButton > button:active { transform:translateY(0) !important; }
.stButton > button:disabled {
    background: var(--border) !important;
    color: var(--muted) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--panel) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    color: var(--muted) !important;
    background: transparent !important;
    border-radius: 7px !important;
    border: none !important;
    padding: 0.45rem 1.1rem !important;
}
.stTabs [aria-selected="true"] {
    background: var(--accent) !important;
    color: #080C14 !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: var(--card) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: 10px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 1rem 1.1rem !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.65rem !important;
    color: var(--muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
[data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
    font-size: 1.5rem !important;
    color: var(--text) !important;
}

/* ── DataFrame ── */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    overflow: hidden;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.8rem !important;
    color: var(--muted) !important;
}

/* ── Alerts ── */
.stAlert { border-radius: 8px !important; font-family: 'DM Mono', monospace !important; }

/* ── Radio ── */
[data-testid="stRadio"] label {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.82rem !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.4rem;">
        <span style="font-size:2rem;">🔬</span>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:1.5rem;
                        font-weight:800;color:#E2E8F0;letter-spacing:-0.03em;">
                Neykuri
            </div>
            <div style="font-family:'DM Mono',monospace;font-size:0.62rem;
                        color:#38BDF8;letter-spacing:0.14em;text-transform:uppercase;">
                Siddha · Edge AI · v1
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown(
        '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
        'color:#64748B;text-transform:uppercase;letter-spacing:0.1em;margin:0 0 4px;">Patient ID</p>',
        unsafe_allow_html=True,
    )
    patient_id = st.text_input("pid", placeholder="e.g. PT-00142",
                               label_visibility="collapsed")

    st.markdown(
        '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
        'color:#64748B;text-transform:uppercase;letter-spacing:0.1em;margin:8px 0 4px;">Image Source</p>',
        unsafe_allow_html=True,
    )
    input_mode = st.radio("src", ["📁 File Upload", "📷 Camera"],
                          label_visibility="collapsed")

    st.divider()

    st.markdown(
        '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
        'color:#64748B;text-transform:uppercase;letter-spacing:0.1em;margin:0 0 6px;">Backend Status</p>',
        unsafe_allow_html=True,
    )
    if st.button("Check Connection", use_container_width=True):
        h = backend_health()
        if h.get("model_loaded"):
            st.success("✅  Online · Model ready")
        elif h.get("status") != "unreachable":
            st.warning("⏳  Online · Loading model…")
        else:
            st.error("❌  Cannot reach API")

    st.divider()
    st.markdown("""
    <div style="font-family:'DM Mono',monospace;font-size:0.62rem;
                color:#1E3A5F;line-height:2;">
        <div>▸ Jetson Nano optimised</div>
        <div>▸ Model loaded once</div>
        <div>▸ Images stored as .jpg</div>
        <div>▸ SQLite — paths only</div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_analyze, tab_history, tab_legend = st.tabs([
    "🔬  Analyse Sample",
    "📋  72-Hour History",
    "📖  Dosha Legend",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1  —  ANALYSE
# ══════════════════════════════════════════════════════════════════════════════
with tab_analyze:
    st.markdown("## Analyse Sample")
    st.caption("Submit a biological fluid image for Dosha classification · up to 9 samples over 72 hours.")

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── Left: controls ────────────────────────────────────────────────────
    with col_left:
        image_bytes, filename = None, None

        if input_mode == "📁 File Upload":
            uploaded = st.file_uploader(
                "Drop sample image here",
                type=["jpg", "jpeg", "png"],
                label_visibility="collapsed",
            )
            if uploaded:
                image_bytes = uploaded.getvalue()
                filename    = uploaded.name
        else:
            cam = st.camera_input("Capture sample")
            if cam:
                image_bytes = cam.getvalue()
                filename    = "camera_capture.jpg"

        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)

        can_submit = bool(patient_id and image_bytes)
        st.button(
            "▶  Run Neykuri Analysis",
            key="run_btn",
            type="primary",
            disabled=not can_submit,
            use_container_width=True,
        )

        if not patient_id:
            st.warning("Enter a Patient ID in the sidebar.")
        if not image_bytes:
            st.info("Upload or capture a sample image.")

    # ── Right: preview ────────────────────────────────────────────────────
    with col_right:
        if image_bytes:
            st.image(image_bytes, caption="Sample preview", use_container_width=True)
        else:
            st.markdown("""
            <div style="border:1.5px dashed #1E2A40;border-radius:12px;
                        height:260px;display:flex;flex-direction:column;
                        align-items:center;justify-content:center;gap:8px;">
                <span style="font-size:3rem;opacity:0.15;">🧫</span>
                <span style="font-family:'DM Mono',monospace;font-size:0.7rem;
                             color:#1E3A5F;letter-spacing:0.1em;">SAMPLE PREVIEW</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Submit ────────────────────────────────────────────────────────────
    if st.session_state.get("run_btn") and can_submit:
        with st.spinner("Sending to Neykuri backend…"):
            try:
                result = call_analyze(patient_id, image_bytes, filename)
            except requests.exceptions.ConnectionError:
                st.error("❌  Cannot reach API at 127.0.0.1:8000")
                st.stop()
            except requests.exceptions.HTTPError as exc:
                try:
                    detail = exc.response.json().get("detail", str(exc))
                except Exception:
                    detail = str(exc)
                st.error(f"❌  {detail}")
                st.stop()

        d     = result["diagnosis"]
        meta  = DOSHA_META.get(d, {"color":"#64748B","icon":"◎","desc":""})
        conf  = result["confidence"]
        ist   = to_ist(result["timestamp"])

        st.divider()

        # ── Diagnosis result using native Streamlit components ────────────
        st.markdown(
            f'<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
            f'color:#64748B;text-transform:uppercase;letter-spacing:0.12em;margin:0;">Diagnosis Result</p>',
            unsafe_allow_html=True,
        )

        # Big dosha name using st.markdown (single safe block, not inside columns)
        st.markdown(
            f'<div style="background:#141B2D;border:1px solid {meta["color"]}44;'
            f'border-left:4px solid {meta["color"]};border-radius:12px;'
            f'padding:1.2rem 1.6rem;margin:0.6rem 0 1rem;">'
            f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
            f'color:#64748B;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:4px;">'
            f'Dosha Detected</div>'
            f'<div style="font-family:\'Syne\',sans-serif;font-weight:800;font-size:2rem;'
            f'color:{meta["color"]};letter-spacing:-0.02em;">'
            f'{meta["icon"]} {d}</div>'
            f'<div style="font-family:\'DM Mono\',monospace;font-size:0.78rem;'
            f'color:#94A3B8;margin-top:6px;">{meta["desc"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Metrics row — pure Streamlit, no HTML
        m1, m2, m3 = st.columns(3)
        m1.metric("Confidence",      f"{conf:.1f}%")
        m2.metric("Patient ID",      result["patient_id"])
        m3.metric("Time (IST)",      ist)

        # Confidence progress bar — pure Streamlit
        st.progress(int(conf), text=f"Confidence: {conf:.1f}%")

        # Raw JSON
        with st.expander("Raw API response"):
            st.code(json.dumps(result, indent=2), language="json")

        # Auto-load history
        st.divider()
        st.markdown(
            '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
            'color:#64748B;text-transform:uppercase;letter-spacing:0.12em;">Updated History</p>',
            unsafe_allow_html=True,
        )
        try:
            hist    = call_history(patient_id)
            records = hist.get("records", [])
            if records:
                df = pd.DataFrame(records)
                df["Date & Time (IST)"] = df["timestamp"].apply(to_ist)
                df["Confidence %"]      = df["confidence"].round(2)
                st.dataframe(
                    df[["record_id","patient_id","prediction","Confidence %","Date & Time (IST)"]].rename(
                        columns={"record_id":"ID","patient_id":"Patient","prediction":"Dosha"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Confidence %": st.column_config.ProgressColumn(
                            "Confidence %", format="%.1f%%", min_value=0, max_value=100
                        )
                    },
                )
                # Mini trend
                trend = df[["Confidence %"]].copy()
                trend.index = range(1, len(trend)+1)
                trend.index.name = "Sample #"
                st.line_chart(trend, use_container_width=True, height=140)
        except Exception:
            st.caption("History will load after first record is saved.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2  —  72-HOUR HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("## 72-Hour Diagnostic Timeline")
    st.caption("Last 9 sequential observations per patient · Timestamps in IST")

    hc1, hc2 = st.columns([2, 1])
    with hc1:
        hist_pid = st.text_input(
            "Patient ID", value=patient_id,
            placeholder="e.g. PT-00142", key="hist_pid",
            label_visibility="collapsed",
        )
    with hc2:
        fetch_btn = st.button("🔍  Load History", type="primary",
                              disabled=not hist_pid, use_container_width=True)

    if not hist_pid:
        st.info("Enter a Patient ID above.")

    if fetch_btn and hist_pid:
        with st.spinner("Fetching records…"):
            try:
                hist_data = call_history(hist_pid)
            except requests.exceptions.ConnectionError:
                st.error("❌  Cannot reach API.")
                st.stop()
            except requests.exceptions.HTTPError as exc:
                if exc.response.status_code == 404:
                    st.warning(f"No records found for **{hist_pid}**.")
                else:
                    st.error(str(exc))
                st.stop()

        records = hist_data.get("records", [])
        if not records:
            st.info("No records returned.")
            st.stop()

        st.success(f"**{len(records)}** record(s) for patient **{hist_pid}**")

        df = pd.DataFrame(records)
        df["Date & Time (IST)"] = df["timestamp"].apply(to_ist)
        df["Confidence %"]      = df["confidence"].round(2)
        df["Sample #"]          = range(1, len(df)+1)

        # ── Charts ────────────────────────────────────────────────────────
        ch1, ch2 = st.columns(2, gap="large")
        with ch1:
            st.markdown(
                '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
                'color:#64748B;text-transform:uppercase;letter-spacing:0.1em;">Confidence Trend</p>',
                unsafe_allow_html=True,
            )
            trend = df[["Sample #","Confidence %"]].set_index("Sample #")
            st.line_chart(trend, use_container_width=True, height=200)

        with ch2:
            st.markdown(
                '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
                'color:#64748B;text-transform:uppercase;letter-spacing:0.1em;">Dosha Distribution</p>',
                unsafe_allow_html=True,
            )
            dist = df["prediction"].value_counts().rename_axis("Dosha").reset_index(name="Count")
            st.bar_chart(dist.set_index("Dosha"), use_container_width=True, height=200)

        # ── Full table ────────────────────────────────────────────────────
        st.markdown(
            '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
            'color:#64748B;text-transform:uppercase;letter-spacing:0.1em;margin-top:1rem;">All Records</p>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            df[["Sample #","prediction","Confidence %","Date & Time (IST)","record_id"]].rename(
                columns={"prediction":"Dosha","record_id":"ID"}
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Confidence %": st.column_config.ProgressColumn(
                    "Confidence %", format="%.1f%%", min_value=0, max_value=100
                )
            },
        )

        # ── Timeline list — each entry is a standalone st.markdown block ──
        st.markdown(
            '<p style="font-family:\'DM Mono\',monospace;font-size:0.65rem;'
            'color:#64748B;text-transform:uppercase;letter-spacing:0.1em;margin-top:1rem;">Visual Timeline</p>',
            unsafe_allow_html=True,
        )
        for _, row in df.iterrows():
            meta  = DOSHA_META.get(row["prediction"], {"color":"#64748B","icon":"◎"})
            color = meta["color"]
            # Each timeline row is a single st.markdown block — safe to render
            st.markdown(
                f'<div style="display:flex;gap:12px;align-items:stretch;margin-bottom:6px;">'
                f'<div style="display:flex;flex-direction:column;align-items:center;padding-top:4px;width:12px;">'
                f'<div style="width:12px;height:12px;border-radius:50%;background:{color};'
                f'box-shadow:0 0 8px {color}88;flex-shrink:0;"></div>'
                f'<div style="flex:1;width:2px;background:#1E2A40;margin-top:3px;min-height:12px;"></div>'
                f'</div>'
                f'<div style="flex:1;background:#141B2D;border:1px solid #1E2A40;'
                f'border-radius:8px;padding:0.65rem 1rem;margin-bottom:2px;">'
                f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;">'
                f'<span style="font-family:\'Syne\',sans-serif;font-weight:700;'
                f'font-size:0.95rem;color:{color};">{meta["icon"]} {row["prediction"]}</span>'
                f'<span style="font-family:\'DM Mono\',monospace;font-size:0.68rem;'
                f'color:#64748B;">{row["Date & Time (IST)"]}</span>'
                f'</div>'
                f'<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;'
                f'color:#94A3B8;margin-top:3px;">'
                f'Confidence <span style="color:{color};font-weight:600;">{row["Confidence %"]:.1f}%</span>'
                f' · Record #{int(row["record_id"])}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        with st.expander("Raw JSON"):
            st.code(json.dumps(hist_data, indent=2), language="json")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3  —  DOSHA LEGEND
# ══════════════════════════════════════════════════════════════════════════════
with tab_legend:
    st.markdown("## Dosha Classification Reference")
    st.caption("Five output classes of the Neykuri DenseNet121 model · Siddha medicine interpretations")

    for i, (name, meta) in enumerate(DOSHA_META.items()):
        # Each legend card is a standalone single st.markdown — never inside columns
        st.markdown(
            f'<div style="background:#141B2D;border:1px solid {meta["color"]}33;'
            f'border-left:4px solid {meta["color"]};border-radius:12px;'
            f'padding:1.1rem 1.4rem;margin-bottom:10px;">'
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">'
            f'<span style="font-size:1.5rem;">{meta["icon"]}</span>'
            f'<div>'
            f'<div style="font-family:\'Syne\',sans-serif;font-weight:800;'
            f'font-size:1.1rem;color:{meta["color"]};">{name}</div>'
            f'<div style="font-family:\'DM Mono\',monospace;font-size:0.62rem;'
            f'color:#64748B;letter-spacing:0.08em;">CLASS {i}</div>'
            f'</div></div>'
            f'<div style="font-family:\'DM Mono\',monospace;font-size:0.78rem;'
            f'color:#94A3B8;line-height:1.6;">{meta["desc"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )