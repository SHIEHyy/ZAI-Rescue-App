import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from streamlit_autorefresh import st_autorefresh

# Page Config
st.set_page_config(page_title="Z.AI Rescue Command", page_icon="🚁", layout="wide")

# Firebase Setup 
if not firebase_admin._apps:
    creds_dict = dict(st.secrets["firebase"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client(database_id="shakehand")


# Custom CSS for a clean, dark "Command Center" aesthetic
st.markdown("""
    <style>
    .stMetric { 
        background-color: #161b22; 
        border: 1px solid #30363d; 
        padding: 15px; 
        border-radius: 10px; 
        color: #ffffff !important; 
    }
    div[data-testid="stMetricLabel"] > div {
        color: #8b949e !important; 
    }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚁 Z.AI Mission Control")
st.caption("Centralized Mesh-Network SOS Management System")
st_autorefresh(interval=3000, limit=None, key="dashboard_autorefresh")

# --- 2. FETCH DATA FROM FIREBASE ---

def get_cloud_data():
    # Fetch from the 'rescue_missions' collection you created in app.py
    docs = db.collection("rescue_missions").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    data_list = []
    for doc in docs:
        d = doc.to_dict()
        data_list.append({
            "Select": False,
            "ID": d.get("id", "N/A"),
            "Phone": d.get("contact", "N/A"),
            "Reported": d.get("time_str", "N/A"),
            "Status": d.get("status", "Pending"),
            "Priority": d.get("priority", "N/A"),
            "Location": d.get("env", "N/A"),
            "AI Analysis": d.get("ai_analysis", "N/A"),
            "lat": d.get("gps_lat", 3.1390),
            "lon": d.get("gps_lng", 101.6869)
        })
    return pd.DataFrame(data_list)

rescue_df = get_cloud_data()

# Sort the dataframe so Pending is always at the top, Sent is at the bottom
if not rescue_df.empty:
    status_order = {"Pending": 1, "Awaiting": 2, "Sent/En Route": 3, "Rescued ✅": 4}
    rescue_df['sort_key'] = rescue_df['Status'].map(status_order).fillna(5)
    rescue_df = rescue_df.sort_values(['sort_key', 'Reported'], ascending=[True, False]).drop(columns=['sort_key'])
    rescue_df = rescue_df.reset_index(drop=True)

# Function to highlight rows based on Status
def style_dataframe(row):
    if row['Status'] == 'Sent/En Route':
        return ['background-color: #0c2b18; color: #8b949e'] * len(row) 
    elif row['Status'] == 'Rescued ✅':
        return ['background-color: #161b22; color: #484f58'] * len(row) 
    elif row['Status'] == 'Pending' and row['Priority'] == 'P0':
        return ['background-color: #3b1818'] * len(row) 
    return [''] * len(row)

if not rescue_df.empty:
    styled_rescue_df = rescue_df.style.apply(style_dataframe, axis=1)
else:
    styled_rescue_df = rescue_df

# --- 3. TOP METRICS (REAL DATA) ---
m1, m2, m3, m4 = st.columns(4)
total_sos = len(rescue_df)
critical_count = len(rescue_df[rescue_df["Priority"] == "P0"]) if total_sos > 0 else 0
m1.metric("Active SOS", str(total_sos))
m2.metric("Critical (P0)", str(critical_count), delta_color="inverse")
m3.metric("Avg Response", "12m")
m4.metric("System Status", "Live", delta_color="normal")

st.divider()

# --- 4. CLUSTER ALERT ---
if critical_count > 0:
    st.error(f"🚨 **SPATIAL CLUSTER ALERT**: {critical_count} Critical P0 packets detected. Immediate action required.")
else:
    st.success("✅ No critical spatial clusters detected at this time.")

# --- 5. INTERACTIVE MISSION TABLE ---
st.subheader("📋 Active Rescue Queue")
st.info("Directly edit the 'Status' column to update mission progress on the Cloud.")

if not rescue_df.empty:
    # We use data_editor to make the table interactive
    edited_df = st.data_editor(
        styled_rescue_df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Dispatch", default=False),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                help="Update rescue phase",
                options=["Pending", "Awaiting", "Sent/En Route", "Rescued ✅"],
                required=True,
            ),
            "AI Analysis": st.column_config.TextColumn("AI Intelligence", width="large"),
        },
        disabled=["ID", "Phone", "Reported", "Priority", "Location", "AI Analysis"],
        hide_index=True,
        width="stretch",
    )

    # Sync changes back to Firebase
    if st.button("💾 Save & Sync Dashboard to Cloud"):
        with st.spinner("Updating Cloud Database..."):
            for index, row in edited_df.iterrows():
                # Update status in Firestore based on ID
                db.collection("rescue_missions").document(row["ID"]).update({"status": row["Status"]})
        st.success("Mission control database updated via Cloud Sync.")
        st.rerun()
else:
    st.warning("No SOS data found in the cloud database.")

# --- 6. COMMAND ACTIONS & MAP ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("🎮 Dispatch Controls")
    if not rescue_df.empty:
        selected_ids = edited_df[edited_df["Select"] == True]["ID"].tolist()
        
        if selected_ids:
            st.write(f"Targets Selected: {', '.join(selected_ids)}")
            if st.button("🚀 Deploy Swift Water Team", type="primary"):
                with st.status("Assigning Rescuers...", expanded=True):
                    time.sleep(0.5)
                    st.write("🛰️ Pushing coordinates to Boat-7...")
                    time.sleep(0.5)
                    
                    for victim_id in selected_ids:
                        db.collection("rescue_missions").document(victim_id).update({"status": "Sent/En Route"})
                    st.write("✅ Database synced!")
                
                st.toast(f"🚁 Boat-7 Dispatched to {len(selected_ids)} locations!")
                time.sleep(1) 
                
                st.rerun()
        else:
            st.write("No victims selected in table.")

with col_right:
    # Real Map from Firebase Data
    st.subheader("📍 Deployment Map")
    if not rescue_df.empty:
        st.map(rescue_df[['lat', 'lon']], size=20, zoom=12)
    else:
        st.info("Waiting for GPS data...")

# --- 7. FOOTER ---
if st.button("🔄 Refresh Data from Cloud"):
    st.rerun()