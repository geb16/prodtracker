# dashboard/streamlit_app.py
# port for streamlit app: 8501

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from api_client import (
    API_BASE,
    get_pc_events,
    get_pc_metrics,
    get_phone_summary,
    pair_phone,
    send_test_heartbeat,
    trigger_phone_block,
)
from flash_warning import flash_warning
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from streamlit_extras.metric_cards import style_metric_cards
from visual_summary import render_performance_corner

# -------------------------------
# CONFIG
# -------------------------------

STATIC_DIR = Path(__file__).parent / "static"
BEEP_FILE = STATIC_DIR / "beep-warning-6387.mp3"


st.set_page_config(
    page_title="ProdTracker Dashboard",
    page_icon="📈",
    layout="wide",
)


# -------------------------------
# SIDEBAR CONTROLS
# -------------------------------

st.sidebar.header("⚙️ Controls")

refresh = st.sidebar.slider("Auto-refresh (seconds)", 1, 60, 10)
st_autorefresh(interval=refresh * 1000, limit=None, key="live_refresh")
st.cache_data.clear()  # ✅ ensure true real-time updates

st.sidebar.divider()
st.sidebar.subheader("📱 Phone Controls")
device_id = st.sidebar.text_input("Device ID", value="phone-001")
phone_window = st.sidebar.slider("Phone Window (minutes)", 15, 240, 60)

st.sidebar.divider()
st.sidebar.subheader("🔐 Pair phone")
phone_name = st.sidebar.text_input("Phone name", value="Android Phone")
pair_clicked = st.sidebar.button("Pair / Reset Secret")

if pair_clicked:
    try:
        resp = pair_phone(device_id=device_id, name=phone_name)
        st.session_state.paired_secret = resp.get("secret")
        st.sidebar.success("Paired. Secret generated.")
    except Exception as exc:
        st.sidebar.error(f"Pairing failed: {exc}")

if "paired_secret" in st.session_state and st.session_state.paired_secret:
    config = {
        "api_base": API_BASE,
        "device_id": device_id,
        "secret": st.session_state.paired_secret,
    }
    st.sidebar.caption("Use this config on Android. Treat the secret like a password.")
    st.sidebar.code(json.dumps(config, indent=2), language="json")

    try:
        import qrcode

        img = qrcode.make(json.dumps(config))
        buf = BytesIO()
        img.save(buf, kind="PNG")
        st.sidebar.image(buf.getvalue(), caption="Scan to copy config")
    except Exception:
        st.sidebar.caption("Tip: install QR support with `pip install qrcode[pil]` in the dashboard env.")

    st.sidebar.divider()
    st.sidebar.subheader("✅ Test heartbeat")
    test_screen_on = st.sidebar.checkbox("Screen on", value=True)
    test_foreground_app = st.sidebar.text_input("Foreground app", value="youtube")
    send_hb = st.sidebar.button("Send test heartbeat")
    if send_hb:
        try:
            send_test_heartbeat(
                device_id=device_id,
                secret=st.session_state.paired_secret,
                screen_on=test_screen_on,
                foreground_app=test_foreground_app,
            )
            st.sidebar.success("Heartbeat accepted.")
        except Exception as exc:
            st.sidebar.error(f"Heartbeat failed: {exc}")


# -------------------------------
# SESSION STATE
# -------------------------------

if "alerts_enabled" not in st.session_state:
    st.session_state.alerts_enabled = False
if "alerted_events" not in st.session_state:
    st.session_state.alerted_events = set()


# -------------------------------
# FETCH DATA (API ONLY)
# -------------------------------

metrics = get_pc_metrics(last_minutes=60)
events = get_pc_events(limit=30)
phone_data = get_phone_summary(device_id=device_id, minutes=phone_window)

phone = phone_data["phone"]
pc = phone_data["pc"]


# -------------------------------
# HEADER
# -------------------------------

st.markdown("<h2 style='text-align:center;'>ProdTracker — Live Signal:Noise</h2>", unsafe_allow_html=True)
st.divider()


# -------------------------------
# PC METRICS (SQL)
# -------------------------------

snr = metrics.get("snr")
signal = metrics.get("signal", 0)
noise = metrics.get("noise", 0)

col1, col2, col3 = st.columns(3)
col1.metric("📊 Signal:Noise (last 60m)", f"{snr:.2f}" if snr else "n/a")
col2.metric("✅ Signal Events", f"{signal}")
col3.metric("⚠️ Noise Events", f"{noise}")
style_metric_cards(border_left_color="#00C853")

st.divider()
render_performance_corner(metrics)

if st.button("Test Ultimate Alert 🔥"):
    flash_warning("YouTube", "Chrome", duration=6)

# -------------------------------
# PHONE METRICS (REDIS)
# -------------------------------

st.subheader("📱 Phone — Live Activity")

c1, c2, c3 = st.columns(3)
c1.metric("📱 Heartbeats", phone["total"])
c2.metric("📱 Screen ON", phone["screen_on"])
c3.metric("🚨 Distracting Apps", phone["distract"])


# -------------------------------
# PHONE HEATMAP (REDIS)
# -------------------------------

st.subheader("🔥 Phone Activity Heatmap")

series = phone["series"]

if series:
    df_phone = pd.DataFrame(series)

    # ✅ Convert Redis epoch -> datetime
    df_phone["timestamp"] = pd.to_datetime(df_phone["ts"], unit="s", utc=True)
    df_phone["minute"] = df_phone["timestamp"].dt.floor("min")  # pyright: ignore[reportAttributeAccessIssue]

    df_phone["activity"] = df_phone.apply(
        lambda r: (
            "Distract"
            if r.get("foreground_app") and any(k in r["foreground_app"] for k in ["youtube", "tiktok", "reddit"])
            else ("On" if r["screen_on"] else "Off")
        ),
        axis=1,
    )

    heat = df_phone.groupby(["minute", "activity"]).size().reset_index(name="count")

    fig_heat = px.density_heatmap(
        heat,
        x="minute",
        y="activity",
        z="count",
        nbinsx=30,
        color_continuous_scale="RdYlGn_r",
        title="Phone Activity (Redis)",
    )

    st.plotly_chart(fig_heat, width="stretch")

else:
    st.info("No recent phone heartbeats.")


# -------------------------------
# MANUAL BLOCK CONTROL
# -------------------------------

st.divider()
st.subheader("🚨 Live Distraction Block Control")

colB1, colB2, colB3 = st.columns([2, 2, 2])
with colB1:
    block_minutes = st.number_input("Block duration (minutes)", 5, 480, 60, step=5)
with colB2:
    block_reason = st.text_input("Reason", value="dashboard-test")
with colB3:
    trigger_block = st.button("Trigger Block Now 🚫")

if trigger_block:
    try:
        result = trigger_phone_block(
            device_id=device_id,
            minutes=int(block_minutes),
            reason=block_reason,
        )
        st.success(f"Block applied until {result.get('expires_at')}")
    except Exception as exc:
        st.error(f"Failed to trigger block: {exc}")


# -------------------------------
# PC EVENTS TABLE
# -------------------------------

st.subheader("🕓 Recent PC Events")

if not events:
    st.info("No recent events found.")
else:
    for idx, e in enumerate(events):
        cols = st.columns([3, 1, 1])

        cols[0].markdown(f"**{e['timestamp']}** — {e['title']} ({e['app']})")
        tag = "🟢 Signal" if e["prod"] else "🔴 Noise"

        event_key = e.get("id") or f"{e['timestamp']}_{idx}"
        already_alerted = event_key in st.session_state.alerted_events

        if not e["prod"]:
            cols[1].markdown(
                f"<div style='background-color:#f3607d;color:white;padding:5px 10px;border-radius:8px;width:fit-content;'>{tag}</div>",
                unsafe_allow_html=True,
            )
            if not already_alerted:
                flash_warning(e["title"], e["app"], duration=10)
                st.session_state.alerted_events.add(event_key)
        else:
            cols[1].markdown(
                f"<div style='background-color:#90E9B5;color:white;padding:5px 10px;border-radius:8px;width:fit-content;'>{tag}</div>",
                unsafe_allow_html=True,
            )

        if e.get("screenshot") and Path(e["screenshot"]).exists():
            try:
                img = Image.open(e["screenshot"])
                cols[2].image(img, width=100)
            except Exception:
                cols[2].warning("Image load error")

        st.markdown("---")


# -------------------------------
# FOOTER
# -------------------------------

st.markdown("<p style='text-align:center;color:gray;'>© 2024 ProdTracker</p>", unsafe_allow_html=True)
