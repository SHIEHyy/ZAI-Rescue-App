import streamlit as st
import pandas as pd
import random
import json
from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials, firestore
import pydeck as pdk

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Z.AI Rescue Command", page_icon="🚁", layout="wide")

# Database Connection Caching (Prevent duplicate connections)
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

# Custom CSS for Command Center aesthetic 
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

# --- HELPER: Safely parse AI JSON or String (ULTIMATE FAILSAFE) ---
def parse_ai_intel(ai_raw, user_note=""):
    ai_raw = str(ai_raw).strip()
    user_note_clean = str(user_note).strip().lower()
    
    is_guessing = False
    ignore_list = ["how are you", "hi", "hello", "hey", "test", "testing", "good morning", "good afternoon"]
    if user_note_clean in ignore_list or (0 < len(user_note_clean) <= 2):
        is_guessing = True

    ai_intel, ai_res, ai_sup = "-", "-", "-"
    
    if not ai_raw or ai_raw == "N/A" or ai_raw == "-":
        return "-", "-", "-"
        
    if "Pending async" in ai_raw or "network delay" in ai_raw.lower() or "⏳" in ai_raw:
        return ai_raw, "-", "-"

    if ai_raw.startswith("{") and ai_raw.endswith("}"):
        try:
            ai_dict = json.loads(ai_raw)
            ai_intel = str(ai_dict.get("Key Intel", ai_dict.get("intel", "-")))
            ai_res = str(ai_dict.get("Resources", ai_dict.get("resources", "-")))
            ai_sup = str(ai_dict.get("Supplies", ai_dict.get("supplies", "-")))
        except Exception as e:
            ai_intel = f"Sys Error: {str(e)} | Raw: {ai_raw}"

    elif 'Key Intel:' in ai_raw:
        try:
            lines = ai_raw.split('\n')
            for line in lines:
                if 'Key Intel:' in line: 
                    ai_intel = line.split('Key Intel:')[1].strip()
                elif 'Resources:' in line: 
                    ai_res = line.split('Resources:')[1].strip()
                elif 'Supplies:' in line: 
                    ai_sup = line.split('Supplies:')[1].strip()
        except Exception:
            pass
    else:
        ai_intel = ai_raw

    if ai_intel and ai_intel != "-" and not ai_intel.startswith("Sys Error") and not ai_intel.startswith("❌"):
        if is_guessing:
            ai_intel += " (guessing)"
        elif user_note_clean and user_note_clean not in ["-", "n/a", "none"]:
            ai_intel += " (real)"

    return ai_intel, ai_res, ai_sup

# --- 2. FETCH DATA FROM FIREBASE ---
def get_cloud_data():
    if not db:
        return pd.DataFrame()
        
    data_list = []
    try:
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
                wait_seconds = max(0, int(datetime.now(timezone.utc).timestamp() - ts))
                wait_hrs = wait_seconds // 3600
                wait_mins = (wait_seconds % 3600) // 60
                wait_secs = wait_seconds % 60
                
                wait_time = f"{wait_hrs}hr {wait_mins}min {wait_secs}second"
            else:
                time_str = d.get("time_str", "N/A")
                wait_time = "N/A"
                
            fetched_ic = str(d.get("ic", d.get("IC", ""))).strip()
            if fetched_ic and fetched_ic != "None":
                display_id = fetched_ic
            else:
                raw_id = str(d.get("mission_id", d.get("id", "")))
                display_id = raw_id if raw_id and raw_id[0].isdigit() and len(raw_id) >= 12 else generate_mock_ic(doc.id)
                
                try:
                    db.collection("rescue_missions").document(doc.id).update({"ic": display_id})
                except Exception:
                    pass
            
            fetched_note = str(d.get("note", "-")).strip()
            ai_intel, ai_res, ai_sup = parse_ai_intel(d.get("ai_analysis", "N/A"), fetched_note)
                
            priority = d.get("priority", "N/A")
            water = d.get('water', d.get('env', 'N/A'))
            medical = str(d.get("medical", "None"))
            hazards = d.get('tags', 'None')
            
            req_team = analyze_team_requirement(priority, water, medical, hazards)

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
                "Notes": fetched_note, 
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

# Styling function for dataframe rows based on Priority and Status
def style_dataframe(row):
    status = str(row.get('Status', ''))
    if status in ['Rescued ✅', 'Resolved - Safe']:
        return ['background-color: rgba(255, 255, 255, 0.05); color: #8b949e'] * len(row) 
    
    prio = str(row.get('Priority', '')).strip().upper()
    if prio == 'P0':
        return ['background-color: rgba(255, 75, 75, 0.15); color: #ff4b4b; font-weight: bold'] * len(row) 
    elif prio == 'P1':
        return ['background-color: rgba(255, 165, 0, 0.15); color: #ffa500; font-weight: bold'] * len(row) 
    elif prio == 'P2':
        return ['background-color: rgba(255, 236, 139, 0.15); color: #ffec8b'] * len(row) 
    elif prio == 'P3':
        return ['background-color: rgba(139, 233, 253, 0.15); color: #8be9fd'] * len(row) 
        
    return [''] * len(row)


# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.header("🔐 Access Control")
    user_role = st.selectbox("Current Role", ["Admin / Commander", "Operator / Viewer"])
    dynamic_sidebar = st.container()

# --- FRAGMENT (Auto-refresh every 15 seconds) ---
@st.fragment(run_every="15s")
def render_live_dashboard():
    rescue_df = get_cloud_data()

    df_pending = rescue_df[rescue_df['Status'].isin(['Pending Rescue', 'Pending', 'Awaiting'])].copy() if not rescue_df.empty else pd.DataFrame()
    df_active = rescue_df[rescue_df['Status'] == 'Sent/En Route'].copy() if not rescue_df.empty else pd.DataFrame()
    df_completed = rescue_df[rescue_df['Status'].isin(['Rescued ✅', 'Resolved - Safe'])].copy() if not rescue_df.empty else pd.DataFrame()

    # Calculate active units
    active_heli = len(df_active[df_active["🚨 Required Team"].str.contains("Heli|Evac", na=False, case=False)])
    active_boat = len(df_active[df_active["🚨 Required Team"].str.contains("Boat|Swift", na=False, case=False)])
    active_medic = len(df_active[df_active["🚨 Required Team"].str.contains("ALS|BLS|Medic", na=False, case=False)])
    active_4x4 = len(df_active[df_active["🚨 Required Team"].str.contains("4x4", na=False, case=False)])

    base_heli, base_boat, base_medic, base_4x4 = 3, 8, 6, 12

    # Calculate remaining idle units
    idle_heli = max(0, base_heli - active_heli)
    idle_boat = max(0, base_boat - active_boat)
    idle_medic = max(0, base_medic - active_medic)
    idle_4x4 = max(0, base_4x4 - active_4x4)

    with dynamic_sidebar:
        st.divider()
        st.header("🛡️ Live Rescue Units")
        st.metric("🚁 Air Rescue (Heli)", f"{idle_heli} Idle / {active_heli} Active")
        st.metric("🚤 Swift Water Boats", f"{idle_boat} Idle / {active_boat} Active")
        st.metric("🚑 ALS Paramedics", f"{idle_medic} Idle / {active_medic} Active")
        st.metric("🛻 4x4 High-Clearance", f"{idle_4x4} Idle / {active_4x4} Active")
        st.divider()

    m1, m2, m3, m4 = st.columns(4)
    total_sos = len(rescue_df)
    critical_count = len(rescue_df[rescue_df["Priority"] == "P0"]) if total_sos > 0 else 0
    m1.metric("🚨 Total Cases", str(total_sos))
    m2.metric("🆘 Critical (P0)", str(critical_count), delta_color="inverse")
    m3.metric("🚁 En Route", str(len(df_active)))
    m4.metric("✅ Rescued", str(len(df_completed)), delta_color="normal")

    if not rescue_df.empty:
        full_csv = rescue_df.drop(columns=['Doc_ID']).to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Export Full Audit Log", data=full_csv, file_name="ZAI_Mission_Report.csv", mime="text/csv")

    st.divider()

    if critical_count > 0:
        st.markdown(f"<div class='flash-alert'>🚨 SPATIAL CLUSTER ALERT: {critical_count} Critical P0 packets detected. Immediate action required.</div><br>", unsafe_allow_html=True)
    else:
        st.success("✅ No critical spatial clusters detected at this time.")

    st.subheader("🚨 1. Pending Missions (Needs Dispatch)")
    if not df_pending.empty:
        # Set index to Doc_ID to prevent data_editor from resetting checkboxes on refresh
        df_pending = df_pending.set_index("Doc_ID", drop=False)
        
        offline_csv = df_pending.drop(columns=['Doc_ID']).to_csv(index=False).encode('utf-8')
        st.download_button(label="🖨️ Offline Backup (Pending)", data=offline_csv, file_name="ZAI_Offline_Pending.csv", mime="text/csv")
        
        df_pending.insert(0, "🚀 Deploy", False)
        
        select_all_pending = st.checkbox("☑️ Select All Pending Missions", key="select_all_pending")
        if select_all_pending:
            df_pending["🚀 Deploy"] = True
        
        view_columns = ["🚀 Deploy", "Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Phone", "Location", "Hazards", "🤖 AI Intel", "📦 AI Supplies", "Doc_ID"]
        
        edited_pending = st.data_editor(
            df_pending[view_columns].style.apply(style_dataframe, axis=1),
            hide_index=True,
            column_config={
                "🚀 Deploy": st.column_config.CheckboxColumn("Select", default=False),
                "Doc_ID": None, 
            },
            disabled=["Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Phone", "Location", "Hazards", "🤖 AI Intel", "📦 AI Supplies"],
            use_container_width=True,
            height=300,
            key="pending_missions_table"
        )
        
        selected_pending_docs = edited_pending[edited_pending["🚀 Deploy"] == True]["Doc_ID"].tolist()
        
        c1, c2 = st.columns([0.7, 0.3])
        with c1:
            confirm_dispatch = st.checkbox("⚠️ I confirm these units are ready for deployment (Action cannot be easily undone)", key="conf_dispatch")
        with c2:
            btn_disabled = user_role != "Admin / Commander"
            if st.button("🚀 Deploy Selected Teams", type="primary", disabled=btn_disabled, use_container_width=True):
                if not confirm_dispatch:
                    st.warning("Please check the confirmation box before deploying.")
                elif not selected_pending_docs:
                    st.warning("No missions selected.")
                else:
                    with st.spinner("Checking capacity and transmitting dispatch orders..."):
                        try:
                            # Prioritize missions: P0 first, then P1, P2, P3
                            priority_map = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
                            selected_rows = df_pending[df_pending["Doc_ID"].isin(selected_pending_docs)].copy()
                            selected_rows["prio_val"] = selected_rows["Priority"].map(priority_map).fillna(99)
                            selected_rows = selected_rows.sort_values("prio_val")

                            batch = db.batch()
                            timestamp_now = datetime.now(MY_TZ).strftime("%Y-%m-%d %H:%M:%S")
                            
                            deployed_count = 0
                            skipped_count = 0

                            for _, row in selected_rows.iterrows():
                                req_team = row["🚨 Required Team"]
                                doc_id = row["Doc_ID"]
                                ic_val = row["IC / ID"]

                                # Determine needed units for this mission
                                needs_heli = 1 if "Heli" in req_team or "Evac" in req_team else 0
                                needs_boat = 1 if "Boat" in req_team or "Swift" in req_team else 0
                                needs_medic = 1 if "ALS" in req_team or "BLS" in req_team or "Medic" in req_team else 0
                                needs_4x4 = 1 if "4x4" in req_team else 0

                                # Check if we have enough idle capacity
                                if (idle_heli >= needs_heli and idle_boat >= needs_boat and 
                                    idle_medic >= needs_medic and idle_4x4 >= needs_4x4):
                                    
                                    # Deduct from available capacity
                                    idle_heli -= needs_heli
                                    idle_boat -= needs_boat
                                    idle_medic -= needs_medic
                                    idle_4x4 -= needs_4x4

                                    doc_ref = db.collection("rescue_missions").document(doc_id)
                                    batch.update(doc_ref, {
                                        "status": "Sent/En Route",
                                        "ic": str(ic_val),
                                        "timeline": firestore.ArrayUnion([f"Dispatched by {user_role} at {timestamp_now}"])
                                    })
                                    deployed_count += 1
                                else:
                                    skipped_count += 1

                            batch.commit()
                            
                            if deployed_count > 0:
                                st.toast(f"✅ {deployed_count} Teams Deployed based on Priority!")
                            if skipped_count > 0:
                                st.warning(f"⚠️ {skipped_count} missions skipped/delayed due to insufficient Rescue Units.")
                                
                            st.rerun() 
                        except Exception as e:
                            st.error("Failed to dispatch due to network or sync error.")
    else:
        st.info("✅ No pending rescue missions.")

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("🚁 2. Active Deployments (En Route)")
    if not df_active.empty:
        # Set index to Doc_ID to prevent data_editor from resetting checkboxes on refresh
        df_active = df_active.set_index("Doc_ID", drop=False)
        
        df_active.insert(0, "✅ Rescued", False)
        
        select_all_active = st.checkbox("☑️ Select All Active Deployments", key="select_all_active")
        if select_all_active:
            df_active["✅ Rescued"] = True
        
        view_columns_active = ["✅ Rescued", "Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Phone", "Location", "Notes", "🤖 AI Intel", "Doc_ID"]
        
        edited_active = st.data_editor(
            df_active[view_columns_active].style.apply(style_dataframe, axis=1),
            hide_index=True,
            column_config={
                "✅ Rescued": st.column_config.CheckboxColumn("Mark Safe", default=False),
                "Doc_ID": None, 
            },
            disabled=["Priority", "Wait Time", "🚨 Required Team", "IC / ID", "Phone", "Location", "Notes", "🤖 AI Intel"],
            use_container_width=True,
            height=300,
            key="active_missions_table"
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
                                ic_val = df_active[df_active["Doc_ID"] == doc_id]["IC / ID"].iloc[0]
                                batch.update(doc_ref, {
                                    "status": "Rescued ✅",
                                    "ic": str(ic_val),
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

    with st.expander("✅ 3. Rescued Archive & AI Data Log"):
        if not df_completed.empty:
            col_order_completed = ["IC / ID", "Phone", "Reported (MYT)", "Status", "Audit Timeline", "Location", "Hazards", "Medical", "🚨 Required Team"]
            st.dataframe(
                df_completed.style.apply(style_dataframe, axis=1),
                column_order=col_order_completed,
                hide_index=True,
                use_container_width=True
            )
        else:
            st.write("No historical data yet.")

    st.divider()

    st.subheader("📍 Interactive Deployment Map")
    if not rescue_df.empty:
        map_data = rescue_df[['IC / ID', 'lat', 'lon', 'Status', 'Priority', '🚨 Required Team']].copy()
        
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

# --- EXECUTE DASHBOARD FRAGMENT ---
render_live_dashboard()

# --- 7. FOOTER ---
st.divider()
if st.button("🔄 Force Refresh System", use_container_width=True):
    st.rerun()