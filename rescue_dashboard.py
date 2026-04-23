import streamlit as st
import pandas as pd
import random
import json
from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from streamlit_autorefresh import st_autorefresh
import pydeck as pdk

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Z.AI Rescue Command", page_icon="🚁", layout="wide")

# Database Connection Caching (P0 Fix: Prevent duplicate connections)
@st.cache_resource
def init_db():
    if not firebase_admin._apps:
        try:
            creds_dict = dict(st.secrets["firebase"])
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error("Database connection failed. Please check secrets.")
            return None
    try:
        return firestore.client(database_id="shakehand")
    except Exception:
        return None

db = init_db()

# Malaysia Timezone (UTC+8) setup
MY_TZ = timezone(timedelta(hours=8))

# Custom CSS for Command Center aesthetic (Updated to unify Light/Dark Mode)
st.markdown("""
    <style>
    .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    .stMetric { 
        background-color: #161b22 !important; 
        border: 1px solid #30363d !important; 
        padding: 15px !important; 
        border-radius: 10px !important; 
    }
    .stMetric [data-testid="stMetricValue"] * {
        color: #ffffff !important;
    }
    .stMetric [data-testid="stMetricLabel"] * {
        color: #8b949e !important; 
    }
    .flash-alert {
        animation: criticalFlash 1.5s infinite;
        background-color: #FF0000;
        color: white;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
    }
    @keyframes criticalFlash {
        0% { opacity: 1.0; }
        50% { opacity: 0.5; }
        100% { opacity: 1.0; }
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚁 Z.AI Mission Control")
st.caption("🌐 Centralized Mesh-Network SOS Management System")

# Extended refresh rate to 15s to prevent UI flickering and clearing selections
st_autorefresh(interval=15000, limit=None, key="dashboard_autorefresh")

# --- AI TEAM ASSIGNMENT ENGINE ---
def analyze_team_requirement(priority, water, medical, hazards):
    teams = []
    medical_str = str(medical)
    hazard_str = str(hazards)
    water_str = str(water)
    
    if "Bleeding" in medical_str or "Unconscious" in medical_str or priority == "P0":
        teams.append("🚑 ALS Medics")
    if "Hypothermia" in medical_str or "Oxygen" in medical_str:
        teams.append("⚕️ BLS Support")
        
    if "Hips" in water_str or "Chest" in water_str or "Fast" in hazard_str:
        teams.append("🚤 Swift Water Unit")
    elif "Knees" in water_str:
        teams.append("🛻 4x4 Unit")
        
    if "Trapped" in hazard_str or "tree" in hazard_str:
        teams.append("🧗 Tactical Rope Team")
    if "wires" in hazard_str:
        teams.append("⚡ HAZMAT Team")
        
    if not teams:
        teams.append("🚁 Standard Evac")
        
    return " + ".join(teams)

# --- HELPER: Generate Mock ID ---
def generate_mock_ic(doc_id):
    random.seed(doc_id) 
    year = random.randint(50, 99)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    place = random.choice(['14', '10', '01', '07', '08']) 
    last = random.randint(1000, 9999)
    return f"{year:02d}{month:02d}{day:02d}-{place}-{last}"

# --- HELPER: Safely parse AI JSON or String (P0 Fix) ---
def parse_ai_intel(ai_raw):
    ai_raw = str(ai_raw).strip()
    ai_intel, ai_res, ai_sup = "-", "-", "-"
    
    try:
        # Attempt to parse as JSON first
        if ai_raw.startswith("{") and ai_raw.endswith("}"):
            ai_dict = json.loads(ai_raw)
            ai_intel = ai_dict.get("Key Intel", ai_dict.get("intel", "-"))
            ai_res = ai_dict.get("Resources", ai_dict.get("resources", "-"))
            ai_sup = ai_dict.get("Supplies", ai_dict.get("supplies", "-"))
            return ai_intel, ai_res, ai_sup
    except json.JSONDecodeError:
        pass

    # Fallback to safe string parsing without crashing
    lines = ai_raw.split('\n')
    for line in lines:
        if 'Key Intel:' in line: 
            ai_intel = line.split('Key Intel:')[1].strip()
        elif 'Resources:' in line: 
            ai_res = line.split('Resources:')[1].strip()
        elif 'Supplies:' in line: 
            ai_sup = line.split('Supplies:')[1].strip()
            
    return ai_intel, ai_res, ai_sup

# --- 2. FETCH DATA FROM FIREBASE (P0 Fix: Query optimization) ---
def get_cloud_data():
    if not db:
        return pd.DataFrame()
        
    data_list = []
    try:
        # P0: Stop full db stream, use targeted query for relevant statuses
        target_statuses = ['Pending Rescue', 'Pending', 'Awaiting', 'Sent/En Route', 'Rescued ✅', 'Resolved - Safe']
        docs = db.collection("rescue_missions").where(filter=firestore.FieldFilter("status", "in", target_statuses)).stream()
        
        for doc in docs:
            d = doc.to_dict()
            
            ts = d.get("server_timestamp", d.get("timestamp", 0))
            if hasattr(ts, 'timestamp') and callable(ts.timestamp):
                ts = ts.timestamp()
            elif isinstance(ts, datetime):
                ts = ts.timestamp()
                
            if ts > 0:
                time_str = datetime.fromtimestamp(ts, MY_TZ).strftime('%H:%M:%S')
                wait_seconds = datetime.now(timezone.utc).timestamp() - ts
                wait_mins = int(wait_seconds // 60)
                wait_hrs = int(wait_mins // 60)
                if wait_hrs > 0:
                    wait_time = f"{wait_hrs}h {wait_mins % 60}m"
                else:
                    wait_time = f"{wait_mins} min"
            else:
                time_str = d.get("time_str", "N/A")
                wait_time = "N/A"
                
            raw_id = d.get("mission_id", d.get("id", "N/A"))
            display_id = raw_id if raw_id[0].isdigit() and len(raw_id) >= 12 else generate_mock_ic(doc.id)
            
            # Use safe AI parser
            ai_intel, ai_res, ai_sup = parse_ai_intel(d.get("ai_analysis", "N/A"))
                
            priority = d.get("priority", "N/A")
            water = d.get('water', d.get('env', 'N/A'))
            medical = str(d.get("medical", "None"))
            hazards = d.get('tags', 'None')
            
            req_team = analyze_team_requirement(priority, water, medical, hazards)

            # Extract timeline for Audit log (P1)
            timeline_log = " | ".join(d.get("timeline", [])) if isinstance(d.get("timeline"), list) else "-"

            data_list.append({
                "Doc_ID": doc.id, 
                "IC / ID": display_id, 
                "Role": d.get("role", "👤 Victim"),
                "Phone": d.get("contact", "N/A"),
                "Reported (MYT)": time_str,
                "Wait Time": wait_time,
                "Status": d.get("status", "Pending Rescue"),
                "Priority": priority,
                "Location": water, 
                "Hazards": hazards, 
                "Medical": medical,
                "Notes": str(d.get("note", "-")).strip(), 
                "🤖 AI Intel": ai_intel,
                "📦 AI Supplies": ai_sup,
                "🚨 Required Team": req_team,
                "Audit Timeline": timeline_log,
                "lat": d.get("gps_lat", 3.1390),
                "lon": d.get("gps_lng", 101.6869)
            })
    except Exception as e:
        st.error(f"Network Error: Failed to fetch data from cloud. {e}")
        
    return pd.DataFrame(data_list)

rescue_df = get_cloud_data()

# Styling function for history table
def style_dataframe(row):
    if row['Status'] in ['Rescued ✅', 'Resolved - Safe']:
        return ['background-color: #1A1B1E; color: #5C5F66'] * len(row) 
    return [''] * len(row)

# Split DataFrames
df_pending = rescue_df[rescue_df['Status'].isin(['Pending Rescue', 'Pending', 'Awaiting'])].copy() if not rescue_df.empty else pd.DataFrame()
df_active = rescue_df[rescue_df['Status'] == 'Sent/En Route'].copy() if not rescue_df.empty else pd.DataFrame()
df_completed = rescue_df[rescue_df['Status'].isin(['Rescued ✅', 'Resolved - Safe'])].copy() if not rescue_df.empty else pd.DataFrame()

# --- DYNAMIC RESOURCES CALCULATION (P1 Fix) ---
active_heli = len(df_active[df_active["🚨 Required Team"].str.contains("Heli|Evac", na=False, case=False)])
active_boat = len(df_active[df_active["🚨 Required Team"].str.contains("Boat|Swift", na=False, case=False)])
active_medic = len(df_active[df_active["🚨 Required Team"].str.contains("ALS|BLS|Medic", na=False, case=False)])
active_4x4 = len(df_active[df_active["🚨 Required Team"].str.contains("4x4", na=False, case=False)])

base_heli, base_boat, base_medic, base_4x4 = 3, 8, 6, 12

# --- SIDEBAR: ROLE, RESOURCES & EXPORT ---
with st.sidebar:
    st.header("🔐 Access Control")
    user_role = st.selectbox("Current Role", ["Admin / Commander", "Operator / Viewer"])
    
    st.divider()
    st.header("🛡️ Live Rescue Units")
    st.metric("🚁 Air Rescue (Heli)", f"{max(0, base_heli - active_heli)} Idle / {active_heli} Active")
    st.metric("🚤 Swift Water Boats", f"{max(0, base_boat - active_boat)} Idle / {active_boat} Active")
    st.metric("🚑 ALS Paramedics", f"{max(0, base_medic - active_medic)} Idle / {active_medic} Active")
    st.metric("🛻 4x4 High-Clearance", f"{max(0, base_4x4 - active_4x4)} Idle / {active_4x4} Active")
    
    st.divider()
    # Offline Backup (P1 Fix: Disconnect failsafe)
    if not df_pending.empty:
        offline_csv = df_pending.drop(columns=['Doc_ID']).to_csv(index=False).encode('utf-8')
        st.download_button(label="🖨️ Offline Backup (Pending)", data=offline_csv, file_name="ZAI_Offline_Pending.csv", mime="text/csv")


# --- 3. TOP METRICS ---
m1, m2, m3, m4 = st.columns(4)
total_sos = len(rescue_df)
critical_count = len(rescue_df[rescue_df["Priority"] == "P0"]) if total_sos > 0 else 0
m1.metric("🚨 Total Cases", str(total_sos))
m2.metric("🆘 Critical (P0)", str(critical_count), delta_color="inverse")
m3.metric("🚁 En Route", str(len(df_active)))
m4.metric("✅ Rescued", str(len(df_completed)), delta_color="normal")

# CSV Export Button for all data
if not rescue_df.empty:
    full_csv = rescue_df.drop(columns=['Doc_ID']).to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="📥 Export Full Audit Log", data=full_csv, file_name="ZAI_Mission_Report.csv", mime="text/csv")

st.divider()

# --- 4. CLUSTER ALERT ---
if critical_count > 0:
    st.markdown(f"<div class='flash-alert'>🚨 SPATIAL CLUSTER ALERT: {critical_count} Critical P0 packets detected. Immediate action required.</div><br>", unsafe_allow_html=True)
else:
    st.success("✅ No critical spatial clusters detected at this time.")

# ==========================================
# UI 1: PENDING (P0 Fix: Replaced stretching loops with Data Editor)
# ==========================================
st.subheader("🚨 1. Pending Missions (Needs Dispatch)")
if not df_pending.empty:
    df_pending.insert(0, "🚀 Deploy", False)
    
    # Bulk Action: Select All Pending
    select_all_pending = st.checkbox("☑️ Select All Pending Missions", key="select_all_pending")
    if select_all_pending:
        df_pending["🚀 Deploy"] = True
    
    # Hide technical columns but keep them available for logic
    view_columns = ["🚀 Deploy", "Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Location", "Hazards", "🤖 AI Intel", "📦 AI Supplies", "Doc_ID"]
    
    edited_pending = st.data_editor(
        df_pending[view_columns],
        hide_index=True,
        column_config={
            "🚀 Deploy": st.column_config.CheckboxColumn("Select", default=False),
            "Doc_ID": None, # Hidden
        },
        disabled=["Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Location", "Hazards", "🤖 AI Intel", "📦 AI Supplies"],
        use_container_width=True,
        height=300
    )
    
    selected_pending_docs = edited_pending[edited_pending["🚀 Deploy"] == True]["Doc_ID"].tolist()
    
    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        confirm_dispatch = st.checkbox("⚠️ I confirm these units are ready for deployment (Action cannot be easily undone)", key="conf_dispatch")
    with c2:
        btn_disabled = user_role != "Admin / Commander"
        # P1 Fix: Prevent double clicking with spinner/processing lock
        if st.button("🚀 Deploy Selected Teams", type="primary", disabled=btn_disabled, use_container_width=True):
            if not confirm_dispatch:
                st.warning("Please check the confirmation box before deploying.")
            elif not selected_pending_docs:
                st.warning("No missions selected.")
            else:
                with st.spinner("Transmitting dispatch orders to field units..."):
                    try:
                        batch = db.batch()
                        timestamp_now = datetime.now(MY_TZ).strftime("%Y-%m-%d %H:%M:%S")
                        for doc_id in selected_pending_docs:
                            doc_ref = db.collection("rescue_missions").document(doc_id)
                            batch.update(doc_ref, {
                                "status": "Sent/En Route",
                                "timeline": firestore.ArrayUnion([f"Dispatched by {user_role} at {timestamp_now}"])
                            })
                        batch.commit()
                        st.toast("✅ Teams Deployed! Database Batch committed.")
                        st.rerun()
                    except Exception as e:
                        st.error("Failed to dispatch due to network or sync error.")
else:
    st.info("✅ No pending rescue missions.")

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# UI 2: ACTIVE DEPLOYMENTS (Data Editor) 
# ==========================================
st.subheader("🚁 2. Active Deployments (En Route)")
if not df_active.empty:
    df_active.insert(0, "✅ Rescued", False)
    
    # Bulk Action: Select All Active
    select_all_active = st.checkbox("☑️ Select All Active Deployments", key="select_all_active")
    if select_all_active:
        df_active["✅ Rescued"] = True
    
    view_columns_active = ["✅ Rescued", "Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Location", "Notes", "🤖 AI Intel", "Doc_ID"]
    
    edited_active = st.data_editor(
        df_active[view_columns_active],
        hide_index=True,
        column_config={
            "✅ Rescued": st.column_config.CheckboxColumn("Mark Safe", default=False),
            "Doc_ID": None, # Hidden
        },
        disabled=["Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Location", "Notes", "🤖 AI Intel"],
        use_container_width=True,
        height=300
    )
    
    selected_active_docs = edited_active[edited_active["✅ Rescued"] == True]["Doc_ID"].tolist()

    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        confirm_resolve = st.checkbox("⚠️ I verify visual or radio confirmation that victims are secured.", key="conf_resolve")
    with c2:
        btn_disabled = user_role != "Admin / Commander"
        if st.button("💾 Confirm Rescued", type="primary", disabled=btn_disabled, use_container_width=True):
            if not confirm_resolve:
                st.warning("Please check the verification box before closing cases.")
            elif not selected_active_docs:
                st.warning("No missions selected.")
            else:
                with st.spinner("Updating database and archiving missions..."):
                    try:
                        batch = db.batch()
                        timestamp_now = datetime.now(MY_TZ).strftime("%Y-%m-%d %H:%M:%S")
                        for doc_id in selected_active_docs:
                            doc_ref = db.collection("rescue_missions").document(doc_id)
                            batch.update(doc_ref, {
                                "status": "Rescued ✅",
                                "timeline": firestore.ArrayUnion([f"Resolved by {user_role} at {timestamp_now}"])
                            })
                        batch.commit()
                        st.toast("✅ Victims marked as Rescued! Moved to Archive.")
                        st.rerun()
                    except Exception as e:
                        st.error("Failed to resolve missions. DB connection issue.")
else:
    st.info("No active deployments at the moment.")

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# TABLE 3: ARCHIVE (Completed Rescues)
# ==========================================
with st.expander("✅ 3. Rescued Archive & AI Data Log"):
    if not df_completed.empty:
        col_order_completed = ["IC / ID", "Reported (MYT)", "Status", "Audit Timeline", "Location", "Hazards", "Medical", "🚨 Required Team"]
        st.dataframe(
            df_completed.style.apply(style_dataframe, axis=1),
            column_order=col_order_completed,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.write("No historical data yet.")

st.divider()

# ==========================================
# DEPLOYMENT MAP (P1 Fix: Auto-scaling viewport)
# ==========================================
st.subheader("📍 Interactive Deployment Map")
if not rescue_df.empty:
    map_data = rescue_df[['IC / ID', 'lat', 'lon', 'Status', 'Priority', '🚨 Required Team']].copy()
    
    # Clean map data dropna to prevent rendering crash
    map_data = map_data.dropna(subset=['lat', 'lon'])
    
    def get_map_color(status):
        if status in ['Pending Rescue', 'Pending', 'Awaiting']: 
            return [255, 75, 75, 200] 
        elif status in ['Sent/En Route']: 
            return [77, 171, 247, 200] 
        else: 
            return [85, 85, 85, 100] 
            
    map_data['color_rgba'] = map_data['Status'].apply(get_map_color)
    
    layer = pdk.Layer(
        'ScatterplotLayer',
        data=map_data,
        get_position='[lon, lat]',
        get_color='color_rgba',
        get_radius=300,
        pickable=True
    )
    
    # Auto scale viewport
    avg_lat = map_data['lat'].mean() if not map_data.empty else 3.1390
    avg_lon = map_data['lon'].mean() if not map_data.empty else 101.6869
    
    view_state = pdk.ViewState(
        latitude=avg_lat, 
        longitude=avg_lon, 
        zoom=11, 
        pitch=0
    )
    
    r = pdk.Deck(
        layers=[layer], 
        initial_view_state=view_state, 
        tooltip={"text": "ID: {IC / ID}\nStatus: {Status}\nPriority: {Priority}\nTeam: {🚨 Required Team}"}
    )
    
    st.pydeck_chart(r)
    
    st.markdown("""
    <div style="background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; font-size: 14px;">
        <b>🗺️ Map Legend (Hover over dots for AI Intel):</b><br><br>
        <span style="color: #FF4B4B; font-size: 18px;">●</span> <b>Pending</b> (SOS Active)<br>
        <span style="color: #4DABF7; font-size: 18px;">●</span> <b>En Route</b> (Rescue Coming)<br>
        <span style="color: #555555; font-size: 18px;">●</span> <b>Rescued</b> (Safe/Resolved)
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("📡 Waiting for GPS data...")

# --- 7. FOOTER ---
st.divider()
if st.button("🔄 Force Refresh System", use_container_width=True):
    st.rerun()