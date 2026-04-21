import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Z.AI Rescue Command", page_icon="🚁", layout="wide")

# Custom CSS for a clean, dark "Command Center" aesthetic
st.markdown("""
    <style>
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚁 Z.AI Mission Control")
st.caption("Centralized Mesh-Network SOS Management System")

# --- 2. SESSION STATE DATA ---
# This ensures the data stays consistent during your demo
if 'rescue_df' not in st.session_state:
    now = datetime.now()
    data = [
        {
            "Select": False,
            "ID": "ZA-101",
            "Phone": "+60 12-345 6789",
            "Reported": (now - timedelta(minutes=28)).strftime("%H:%M"),
            "Wait Time": "28m",
            "Status": "Pending",
            "Priority": "P0 - Critical",
            "Location": "Rooftop"
        },
        {
            "Select": False,
            "ID": "ZA-102",
            "Phone": "+60 19-888 2211",
            "Reported": (now - timedelta(minutes=15)).strftime("%H:%M"),
            "Wait Time": "15m",
            "Status": "Awaiting",
            "Priority": "P1 - High",
            "Location": "Upper Floor"
        },
        {
            "Select": False,
            "ID": "ZA-103",
            "Phone": "+60 11-222 3333",
            "Reported": (now - timedelta(minutes=5)).strftime("%H:%M"),
            "Wait Time": "5m",
            "Status": "Sent/En Route",
            "Priority": "P2 - Medium",
            "Location": "Ground Level"
        }
    ]
    st.session_state.rescue_df = pd.DataFrame(data)

# --- 3. TOP METRICS ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("Active SOS", "14", "+2")
m2.metric("Critical (P0)", "3", delta_color="inverse")
m3.metric("Avg Response", "12m")
m4.metric("Rescued Today", "42", "Check", delta_color="normal")

st.divider()

# --- 4. CLUSTER ALERT (Killer Feature) ---
st.error("🚨 **SPATIAL CLUSTER ALERT**: 12 High-Density Packets detected in Section 17. Possible mass casualty site.")

# --- 5. INTERACTIVE MISSION TABLE ---
st.subheader("📋 Active Rescue Queue")
st.info("Directly edit the 'Status' or 'Select' columns below to update mission progress.")

# We use data_editor to make the table interactive
edited_df = st.data_editor(
    st.session_state.rescue_df,
    column_config={
        "Select": st.column_config.CheckboxColumn("Dispatch", default=False),
        "Status": st.column_config.SelectboxColumn(
            "Status",
            help="Update rescue phase",
            options=["Pending", "Awaiting", "Sent/En Route", "Rescued ✅"],
            required=True,
        ),
        "Priority": st.column_config.TextColumn("Priority", disabled=True),
        "ID": st.column_config.TextColumn("Victim ID", disabled=True),
    },
    disabled=["ID", "Phone", "Reported", "Wait Time", "Priority", "Location"],
    hide_index=True,
    use_container_width=True,
)

# Sync changes back to session state
if st.button("💾 Save & Sync Dashboard"):
    st.session_state.rescue_df = edited_df
    st.success("Mission control database updated via Mesh-Relay.")

# --- 6. COMMAND ACTIONS & MAP ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("🎮 Dispatch Controls")
    selected_ids = edited_df[edited_df["Select"] == True]["ID"].tolist()
    
    if selected_ids:
        st.write(f"Targets Selected: {', '.join(selected_ids)}")
        if st.button("🚀 Deploy Swift Water Team", type="primary"):
            with st.status("Assigning Rescuers..."):
                time.sleep(1)
                st.write("Pushing coordinates to Boat-7...")
            st.toast(f"Boat-7 Dispatched to {len(selected_ids)} locations!")
    else:
        st.write("No victims selected in table.")

with col_right:
    # Minimalist Map
    st.subheader("📍 Deployment Map")
    map_data = pd.DataFrame({
        'lat': [3.1390, 3.1410, 3.1350],
        'lon': [101.6869, 101.6880, 101.6800]
    })
    st.map(map_data, size=20, zoom=12)

# --- 7. FOOTER ---
if st.button("🔄 Refresh Mesh Packets"):
    st.rerun()