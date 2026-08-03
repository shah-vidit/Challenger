import streamlit as st
import pandas as pd
import pymysql
import pymysql.cursors
from datetime import datetime, timedelta
import time

# ==========================================
# 1. APP CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="Fintech Speed Lab", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E6ED; }
    .main-header { font-size: 2.5rem; font-weight: 900; color: #00FFAA; text-align: center; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 0px; }
    .dev-credit { text-align: center; color: #8892B0; font-size: 0.9rem; margin-top: -5px; margin-bottom: 30px; letter-spacing: 1px; text-transform: uppercase; }
    .challenge-card { border: 1px solid #2e364a; padding: 20px; border-radius: 10px; margin-bottom: 15px; background-color: #161b26; }
    .locked-card { border: 1px dashed #424959; padding: 20px; border-radius: 10px; margin-bottom: 15px; background-color: #0E1117; color: #5c667a; opacity: 0.7;}
    </style>
""", unsafe_allow_html=True)

TOLERANCE = 0.01

# ==========================================
# 2. DATABASE CONNECTION (THREAD-SAFE)
# ==========================================
def get_db_connection():
    return pymysql.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def run_query(query, params=None, fetch=True):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            return cursor.lastrowid
    finally:
        conn.close()

# ==========================================
# 3. SESSION STATE INITIALIZATION
# ==========================================
for key in ['logged_in', 'admin_mode']:
    if key not in st.session_state:
        st.session_state[key] = False
for key in ['pod_num', 'team_name']:
    if key not in st.session_state:
        st.session_state[key] = None

# ==========================================
# 4. MISSION STUDIO POP-UP DIALOG (V9)
# ==========================================
@st.dialog("🚀 Mission Studio & Management", width="large")
def mission_studio():
    tab_create, tab_manage = st.tabs(["➕ Create New Mission", "🛠️ Manage Existing Missions"])
    
    # --- TAB 1: CREATE ---
    with tab_create:
        st.markdown("### Draft a New Case Study")
        with st.form("deploy_mission_form"):
            m_title = st.text_input("Mission Title", "Day 3: Bank Stress Test")
            m_brief = st.text_area("CFO Brief (Markdown Supported)", "Analyze the incoming data feed and clear the challenges.")
            m_file = st.file_uploader("Attach Dataset (Optional)")
            
            st.markdown("**Define Challenges:**")
            default_challenges = pd.DataFrame({
                "Step": [1, 2, 3],
                "Question": ["Net Profit Margin", "Debt-to-Equity", "Current Ratio"],
                "Objective": [
                    "Drop all rows where 'Revenue' is NaN. Calculate Net Income / Revenue.", 
                    "Clean string formatting in Total Debt. Calculate Debt / Equity.", 
                    "Perform EDA to drop outliers in Liabilities. Calculate Assets / Liabilities."
                ],
                "Target": [0.15, 1.25, 1.80]
            })
            
            edited_challenges = st.data_editor(default_challenges, num_rows="dynamic", use_container_width=True)
            
            if st.form_submit_button("💾 SAVE MISSION TO DATABASE"):
                file_name = m_file.name if m_file else None
                file_data = m_file.getvalue() if m_file else None
                
                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        sql = "INSERT INTO MISSION_MASTER (mission_title, mission_brief, file_name, file_data, is_active) VALUES (%s, %s, %s, %s, False)"
                        cursor.execute(sql, (m_title, m_brief, file_name, file_data))
                        new_mission_id = cursor.lastrowid
                        
                        for _, row in edited_challenges.iterrows():
                            c_sql = "INSERT INTO MISSION_CHALLENGES (mission_id, step_number, question_title, objective, target_value) VALUES (%s, %s, %s, %s, %s)"
                            cursor.execute(c_sql, (new_mission_id, row['Step'], row['Question'], row['Objective'], row['Target']))
                        conn.commit()
                    st.success(f"Mission '{m_title}' successfully saved!")
                    time.sleep(1.5)
                    st.rerun()
                finally:
                    conn.close()
                    
    # --- TAB 2: MANAGE & EDIT ---
    with tab_manage:
        st.markdown("### Edit or Delete Missions")
        all_missions = run_query("SELECT * FROM MISSION_MASTER ORDER BY created_at DESC")
        
        if all_missions:
            mission_opts = {f"ID {m['mission_id']}: {m['mission_title']}": m for m in all_missions}
            selected_opt = st.selectbox("Select Mission to Edit", list(mission_opts.keys()))
            m = mission_opts[selected_opt]
            
            status_label = "🟢 LIVE" if m['is_active'] else "⚪ STANDBY"
            st.markdown(f"**Current Status:** {status_label}")
            
            # Form to edit the entire mission
            with st.form(key=f"edit_form_{m['mission_id']}"):
                edit_title = st.text_input("Mission Title", m['mission_title'])
                edit_brief = st.text_area("CFO Brief", m['mission_brief'])
                
                # Dynamic File Uploader Logic
                curr_file = m['file_name'] if m.get('file_name') else "No file attached"
                st.markdown(f"**Current Dataset:** `{curr_file}`")
                edit_file = st.file_uploader("Replace Dataset (Leave blank to keep existing dataset)", key=f"file_edit_{m['mission_id']}")
                
                challs = run_query("SELECT challenge_id, step_number as Step, question_title as Question, objective as Objective, target_value as Target FROM MISSION_CHALLENGES WHERE mission_id = %s ORDER BY step_number ASC", (m['mission_id'],))
                
                if challs:
                    df_challs = pd.DataFrame(challs)
                else:
                    df_challs = pd.DataFrame(columns=["challenge_id", "Step", "Question", "Objective", "Target"])
                
                st.markdown("**Edit Challenges (Step-by-Step):**")
                edited_df = st.data_editor(df_challs, column_config={"challenge_id": None}, num_rows="dynamic", use_container_width=True)
                
                save_btn = st.form_submit_button("💾 OVERWRITE MISSION DATA", type="primary", use_container_width=True)
                
            if save_btn:
                orig_ids = [c['challenge_id'] for c in challs]
                current_ids = []
                
                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        # 1. Update Title, Brief, and File
                        if edit_file:
                            file_name = edit_file.name
                            file_data = edit_file.getvalue()
                            cursor.execute("UPDATE MISSION_MASTER SET mission_title = %s, mission_brief = %s, file_name = %s, file_data = %s WHERE mission_id = %s", (edit_title, edit_brief, file_name, file_data, m['mission_id']))
                        else:
                            cursor.execute("UPDATE MISSION_MASTER SET mission_title = %s, mission_brief = %s WHERE mission_id = %s", (edit_title, edit_brief, m['mission_id']))
                        
                        # 2. Update, Insert, or Delete Challenges
                        for _, row in edited_df.iterrows():
                            cid = row.get('challenge_id', None)
                            if pd.notna(cid):
                                cid = int(cid)
                                current_ids.append(cid)
                                cursor.execute("UPDATE MISSION_CHALLENGES SET step_number=%s, question_title=%s, objective=%s, target_value=%s WHERE challenge_id=%s", (row['Step'], row['Question'], row['Objective'], row['Target'], cid))
                            else:
                                cursor.execute("INSERT INTO MISSION_CHALLENGES (mission_id, step_number, question_title, objective, target_value) VALUES (%s, %s, %s, %s, %s)", (m['mission_id'], row['Step'], row['Question'], row['Objective'], row['Target']))
                        
                        # Remove deleted challenges
                        for oid in orig_ids:
                            if oid not in current_ids:
                                cursor.execute("DELETE FROM MISSION_CHALLENGES WHERE challenge_id = %s", (oid,))
                        
                        conn.commit()
                    st.success("Mission successfully updated!")
                    time.sleep(1)
                    st.rerun()
                finally:
                    conn.close()
            
            st.divider()
            if st.button(f"🗑️ Permanently Delete '{m['mission_title']}'", type="secondary"):
                run_query("DELETE FROM MISSION_MASTER WHERE mission_id = %s", (m['mission_id'],), fetch=False)
                st.toast("Mission Deleted from Database.")
                time.sleep(1)
                st.rerun()
                
        else:
            st.info("No missions available. Create one to get started.")

# ==========================================
# 5. GLOBAL DATA FETCH (Syncs Admin and Pods)
# ==========================================
active_mission_data = run_query("SELECT * FROM MISSION_MASTER WHERE is_active = True LIMIT 1")
mission = active_mission_data[0] if active_mission_data else None

is_time_up = False
is_lab_ended = False
timer_end_time = None

if mission:
    timer_end_time = mission['end_time']
    if timer_end_time:
        is_time_up = datetime.now() >= timer_end_time
    is_lab_ended = mission['is_completed'] or is_time_up

# ==========================================
# 6. SIDEBAR: AUTHENTICATION & ADMIN
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3256/3256114.png", width=80)
    st.title("Terminal Access")
    
    with st.expander("⚙️ Admin Console"):
        admin_pass = st.text_input("Admin Password", type="password")
        if admin_pass == "cfo2026":
            st.session_state.admin_mode = True
            st.success("Admin Access Granted")
            
            st.markdown("### 📡 Live Operations")
            missions = run_query("SELECT mission_id, mission_title, is_active FROM MISSION_MASTER ORDER BY created_at DESC")
            
            if missions:
                mission_dict = {f"ID {m['mission_id']}: {m['mission_title']}": m['mission_id'] for m in missions}
                active_m_title = next((f"ID {m['mission_id']}: {m['mission_title']}" for m in missions if m['is_active']), None)
                
                selected_mission = st.selectbox("Select Mission to Broadcast", options=list(mission_dict.keys()), index=list(mission_dict.keys()).index(active_m_title) if active_m_title else 0)
                
                if st.button("🔴 ACTIVATE SELECTED MISSION", use_container_width=True):
                    run_query("UPDATE MISSION_MASTER SET is_active = False, end_time = NULL, is_completed = False", fetch=False)
                    run_query("UPDATE MISSION_MASTER SET is_active = True WHERE mission_id = %s", (mission_dict[selected_mission],), fetch=False)
                    st.success(f"Mission is now live!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("No missions found in database.")
                
            if st.button("➕ Open Mission Studio", use_container_width=True):
                mission_studio()
            
            st.divider()
            
            if mission:
                st.markdown("### ⏱️ Master Mission Controls")
                col1, col2 = st.columns(2)
                timer_mins = col1.number_input("Set Timer (Mins)", min_value=1, value=15)
                
                if col2.button("▶️ START TIMER", use_container_width=True):
                    new_end_time = datetime.now() + timedelta(minutes=timer_mins)
                    run_query("UPDATE MISSION_MASTER SET end_time = %s, is_completed = False WHERE mission_id = %s", (new_end_time, mission['mission_id']), fetch=False)
                    st.success("Global Timer Started!")
                    time.sleep(1)
                    st.rerun()
                
                if st.button("🏁 HALT TRADING (Reveal Podium)", type="primary", use_container_width=True):
                    run_query("UPDATE MISSION_MASTER SET is_completed = True WHERE mission_id = %s", (mission['mission_id'],), fetch=False)
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("Activate a mission to access timer controls.")
            
        elif admin_pass:
            st.error("Invalid Admin Password")

    st.divider()

    if not st.session_state.logged_in:
        st.subheader("Pod Authentication")
        pod_select = st.selectbox("Select Pod", list(range(1, 14)))
        pod_pass = st.text_input("Pod Password", type="password")
        
        if st.button("LOGIN"):
            user_data = run_query("SELECT * FROM POD_AUTH WHERE pod_number = %s AND pod_password = %s", (pod_select, pod_pass))
            if user_data:
                st.session_state.logged_in = True
                st.session_state.pod_num = pod_select
                st.session_state.team_name = user_data[0]['team_name']
                st.rerun()
            else:
                st.error("Invalid Credentials.")
    else:
        st.success(f"Connected to Pod {st.session_state.pod_num}")
        if st.button("LOGOUT"):
            for key in ['logged_in', 'pod_num', 'team_name']:
                st.session_state[key] = None
            st.rerun()

# ==========================================
# 7. MAIN DASHBOARD & GAMIFIED MISSION LOGIC
# ==========================================
st.markdown("<div class='main-header'>Fintech Speed Lab</div>", unsafe_allow_html=True)
st.markdown("<div class='dev-credit'>Developed by Vidit Shah</div>", unsafe_allow_html=True)

if timer_end_time and not is_lab_ended:
    time_remaining = (timer_end_time - datetime.now()).total_seconds()
    mins, secs = divmod(int(time_remaining), 60)
    st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>⏳ TIME REMAINING: {mins:02d}:{secs:02d}</h2>", unsafe_allow_html=True)
elif is_lab_ended:
    st.markdown("<h2 style='text-align: center; color: #FF4B4B;'>🛑 LAB LOCKED - TRADING HALTED</h2>", unsafe_allow_html=True)

if st.session_state.logged_in:
    
    if not st.session_state.team_name:
        st.warning("⚠️ Name our Hedge Fund/Pod to Unlock the Dashboard!")
        new_team_name = st.text_input("Enter our official Team/Fund Name:")
        if st.button("🚀 Lock In Team Name"):
            if len(new_team_name.strip()) > 2:
                run_query("UPDATE POD_AUTH SET team_name = %s WHERE pod_number = %s", (new_team_name.strip(), st.session_state.pod_num), fetch=False)
                st.session_state.team_name = new_team_name.strip()
                st.rerun()
        st.stop()
    
    st.markdown(f"<h3 style='text-align: center;'>🏦 Fund: <b>{st.session_state.team_name}</b></h3>", unsafe_allow_html=True)
    
    if not mission:
        st.info("📡 Standing by. Awaiting CFO to deploy the next mission...")
    else:
        m_id = mission['mission_id']
        
        with st.expander("📜 VIEW CFO MISSION BRIEF", expanded=False):
            st.markdown(f"### {mission['mission_title']}")
            st.markdown(mission['mission_brief'])
            if mission['file_data']:
                st.divider()
                st.download_button(
                    label=f"📥 ACQUIRE DATASET: {mission['file_name']}",
                    data=mission['file_data'],
                    file_name=mission['file_name'],
                    use_container_width=True
                )

        st.divider()
        
        challenges = run_query("SELECT * FROM MISSION_CHALLENGES WHERE mission_id = %s ORDER BY step_number ASC", (m_id,))
        total_challenges = len(challenges)
        
        progress_data = run_query("SELECT challenge_id FROM CHALLENGE_SUBMISSIONS WHERE pod_number = %s AND mission_id = %s AND is_correct = True", (st.session_state.pod_num, m_id))
        solved_ids = [p['challenge_id'] for p in progress_data] if progress_data else []
        
        current_step_num = 1
        for c in challenges:
            if c['challenge_id'] in solved_ids:
                current_step_num = c['step_number'] + 1
        
        completion_pct = int((len(solved_ids) / total_challenges) * 100) if total_challenges > 0 else 0
        st.markdown(f"### 🎯 Active Operations Status: {completion_pct}%")
        st.progress(completion_pct / 100)
        
        if current_step_num > total_challenges:
            if not is_lab_ended:
                st.balloons()
            st.success("🏆 ALL MISSIONS ACCOMPLISHED! Alpha Generated. The Board is extremely pleased.")
            
        for c in challenges:
            step = c['step_number']
            
            if step < current_step_num:
                st.markdown(f"<div class='challenge-card'><h4>✅ Phase {step} Secured: {c['question_title']}</h4></div>", unsafe_allow_html=True)
            
            elif step == current_step_num:
                st.markdown(f"""
                <div class='challenge-card' style='border-color: #00FFAA; border-width: 2px;'>
                    <h4>▶️ Phase {step}: {c['question_title']}</h4>
                    <p style='color: #8892B0; padding-left: 5px; border-left: 3px solid #FFD700; margin-bottom: 20px;'>
                        <b>Objective:</b> {c['objective']}
                    </p>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    with st.form(key=f"form_step_{step}"):
                        val = st.number_input("Enter Computed Metric:", format="%.2f", disabled=is_lab_ended)
                        
                        audit_code = st.text_area("Audit Trail (Paste your Pandas code here):", 
                                                  placeholder="e.g., df['Revenue'].dropna()...", 
                                                  disabled=is_lab_ended)
                        
                        submit = st.form_submit_button("⚡ EXECUTE TRADE / SUBMIT", disabled=is_lab_ended, use_container_width=True)
                        
                        if submit and not is_lab_ended:
                            if len(audit_code.strip()) < 10:
                                st.toast("❌ Audit Failed. You must provide your Python/Pandas code.", icon="🚨")
                            else:
                                is_correct = bool(abs(val - c['target_value']) <= TOLERANCE)
                                
                                run_query("""
                                    INSERT INTO CHALLENGE_SUBMISSIONS (pod_number, mission_id, challenge_id, submitted_value, is_correct, audit_code) 
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (st.session_state.pod_num, m_id, c['challenge_id'], val, is_correct, audit_code), fetch=False)
                                
                                if is_correct:
                                    st.toast("✅ Metric Validated! Decrypting next phase...", icon="🔓")
                                    time.sleep(1.2)
                                    st.rerun()
                                else:
                                    st.toast("❌ Audit Failed. Recalculate your matrix.", icon="🚨")
                st.markdown("</div>", unsafe_allow_html=True)
            
            else:
                st.markdown(f"<div class='locked-card'><h4>🔒 Phase {step}: Classified (Clear Phase {step-1} to Access)</h4></div>", unsafe_allow_html=True)

st.divider()

# ==========================================
# 8. GAMIFIED LEADERBOARD & PODIUM
# ==========================================
st.markdown("### 🏆 GLOBAL POD LEADERBOARD")

if mission:
    m_id = mission['mission_id']
    total_q = run_query("SELECT COUNT(*) as t FROM MISSION_CHALLENGES WHERE mission_id = %s", (m_id,))[0]['t']
    
    pods_data = run_query("SELECT p.pod_number, COALESCE(p.team_name, 'Unnamed Pod') as team_name, GROUP_CONCAT(DISTINCT s.student_name SEPARATOR ', ') as students FROM POD_AUTH p LEFT JOIN STUDENT_MASTER s ON p.pod_number = s.pod_number GROUP BY p.pod_number, p.team_name")
    subs_data = run_query("SELECT * FROM CHALLENGE_SUBMISSIONS WHERE mission_id = %s ORDER BY submission_time ASC", (m_id,))
    
    df_pods = pd.DataFrame(pods_data)
    
    if subs_data:
        df_subs = pd.DataFrame(subs_data)
        
        BASE_SCORE = 100
        PENALTY_PER_MISS = 15
        SPEED_DEMON_BONUS = 50
        
        scores = []
        
        correct_subs = df_subs[df_subs['is_correct'] == 1]
        first_bloods = correct_subs.drop_duplicates(subset=['challenge_id'], keep='first')
        
        for pod in df_pods['pod_number']:
            pod_subs = df_subs[df_subs['pod_number'] == pod]
            pod_score = 0
            phases_cleared = 0
            badges = []
            
            for c_id in pod_subs['challenge_id'].unique():
                c_attempts = pod_subs[pod_subs['challenge_id'] == c_id]
                if 1 in c_attempts['is_correct'].values:
                    phases_cleared += 1
                    misses = len(c_attempts) - 1
                    
                    points = max(BASE_SCORE - (misses * PENALTY_PER_MISS), 20) 
                    
                    if pod in first_bloods[first_bloods['challenge_id'] == c_id]['pod_number'].values:
                        points += SPEED_DEMON_BONUS
                        badges.append("⚡")
                    
                    pod_score += points
            
            last_act = pod_subs['submission_time'].max() if not pod_subs.empty else pd.NaT
            scores.append({'pod_number': pod, 'Score': pod_score, 'Phases': phases_cleared, 'Last Signal': last_act, 'Badges': "".join(badges)})
            
        df_scores = pd.DataFrame(scores)
        df_master = pd.merge(df_pods, df_scores, on='pod_number', how='left').fillna({'Score': 0, 'Phases': 0, 'Badges': ''})
        
        df_master = df_master.sort_values(by=['Score', 'Last Signal'], ascending=[False, True]).reset_index(drop=True)
        df_master.insert(0, 'Rank', range(1, len(df_master) + 1))
        
        if is_lab_ended:
            st.markdown("<h2 style='text-align: center; color: #FFD700;'>🏁 TRADING HALTED - FINAL RESULTS 🏁</h2>", unsafe_allow_html=True)
            col_2, col_1, col_3 = st.columns([1, 1.2, 1])
            
            if len(df_master) >= 1:
                with col_1:
                    st.markdown(f"<div style='background: #3b2b00; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #FFD700;'><h1 style='margin:0;'>🥇 1ST</h1><h3>{df_master.iloc[0]['team_name']}</h3><h2>{int(df_master.iloc[0]['Score'])} PTS</h2><p style='color: #8892B0;'>{df_master.iloc[0]['students']}</p></div>", unsafe_allow_html=True)
            if len(df_master) >= 2:
                with col_2:
                    st.markdown(f"<div style='background: #161b26; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #C0C0C0; margin-top: 30px;'><h2 style='margin:0;'>🥈 2ND</h2><h4>{df_master.iloc[1]['team_name']}</h4><h3>{int(df_master.iloc[1]['Score'])} PTS</h3></div>", unsafe_allow_html=True)
            if len(df_master) >= 3:
                with col_3:
                    st.markdown(f"<div style='background: #2a1b15; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #CD7F32; margin-top: 50px;'><h3 style='margin:0;'>🥉 3RD</h3><h4>{df_master.iloc[2]['team_name']}</h4><h3>{int(df_master.iloc[2]['Score'])} PTS</h3></div>", unsafe_allow_html=True)
            
            st.divider()
        
        df_display = df_master[['Rank', 'team_name', 'Badges', 'Score', 'Phases']].copy()
        df_display['Phases'] = df_display['Phases'].apply(lambda x: f"{int(x)} / {total_q}")
        df_display = df_display.rename(columns={'team_name': 'Hedge Fund'})
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
    else:
        st.info("Market is quiet. Awaiting first pod transmission...")
else:
    st.info("Leaderboard will populate when a mission is deployed.")
def run_query(query, params=None, fetch=True):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            return cursor.lastrowid
    finally:
        conn.close()

# ==========================================
# 3. SESSION STATE INITIALIZATION
# ==========================================
for key in ['logged_in', 'admin_mode']:
    if key not in st.session_state:
        st.session_state[key] = False
for key in ['pod_num', 'team_name']:
    if key not in st.session_state:
        st.session_state[key] = None

# ==========================================
# 4. MISSION STUDIO POP-UP DIALOG (V9)
# ==========================================
@st.dialog("🚀 Mission Studio & Management", width="large")
def mission_studio():
    tab_create, tab_manage = st.tabs(["➕ Create New Mission", "🛠️ Manage Existing Missions"])
    
    # --- TAB 1: CREATE ---
    with tab_create:
        st.markdown("### Draft a New Case Study")
        with st.form("deploy_mission_form"):
            m_title = st.text_input("Mission Title", "Day 3: Bank Stress Test")
            m_brief = st.text_area("CFO Brief (Markdown Supported)", "Analyze the incoming data feed and clear the challenges.")
            m_file = st.file_uploader("Attach Dataset (Optional)")
            
            st.markdown("**Define Challenges:**")
            default_challenges = pd.DataFrame({
                "Step": [1, 2, 3],
                "Question": ["Net Profit Margin", "Debt-to-Equity", "Current Ratio"],
                "Objective": [
                    "Drop all rows where 'Revenue' is NaN. Calculate Net Income / Revenue.", 
                    "Clean string formatting in Total Debt. Calculate Debt / Equity.", 
                    "Perform EDA to drop outliers in Liabilities. Calculate Assets / Liabilities."
                ],
                "Target": [0.15, 1.25, 1.80]
            })
            
            edited_challenges = st.data_editor(default_challenges, num_rows="dynamic", use_container_width=True)
            
            if st.form_submit_button("💾 SAVE MISSION TO DATABASE"):
                file_name = m_file.name if m_file else None
                file_data = m_file.getvalue() if m_file else None
                
                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        sql = "INSERT INTO MISSION_MASTER (mission_title, mission_brief, file_name, file_data, is_active) VALUES (%s, %s, %s, %s, False)"
                        cursor.execute(sql, (m_title, m_brief, file_name, file_data))
                        new_mission_id = cursor.lastrowid
                        
                        for _, row in edited_challenges.iterrows():
                            c_sql = "INSERT INTO MISSION_CHALLENGES (mission_id, step_number, question_title, objective, target_value) VALUES (%s, %s, %s, %s, %s)"
                            cursor.execute(c_sql, (new_mission_id, row['Step'], row['Question'], row['Objective'], row['Target']))
                        conn.commit()
                    st.success(f"Mission '{m_title}' successfully saved!")
                    time.sleep(1.5)
                    st.rerun()
                finally:
                    conn.close()
                    
    # --- TAB 2: MANAGE & EDIT ---
    with tab_manage:
        st.markdown("### Edit or Delete Missions")
        all_missions = run_query("SELECT * FROM MISSION_MASTER ORDER BY created_at DESC")
        
        if all_missions:
            mission_opts = {f"ID {m['mission_id']}: {m['mission_title']}": m for m in all_missions}
            selected_opt = st.selectbox("Select Mission to Edit", list(mission_opts.keys()))
            m = mission_opts[selected_opt]
            
            status_label = "🟢 LIVE" if m['is_active'] else "⚪ STANDBY"
            st.markdown(f"**Current Status:** {status_label}")
            
            # Form to edit the entire mission
            with st.form(key=f"edit_form_{m['mission_id']}"):
                edit_title = st.text_input("Mission Title", m['mission_title'])
                edit_brief = st.text_area("CFO Brief", m['mission_brief'])
                
                # Dynamic File Uploader Logic
                curr_file = m['file_name'] if m.get('file_name') else "No file attached"
                st.markdown(f"**Current Dataset:** `{curr_file}`")
                edit_file = st.file_uploader("Replace Dataset (Leave blank to keep existing dataset)", key=f"file_edit_{m['mission_id']}")
                
                challs = run_query("SELECT challenge_id, step_number as Step, question_title as Question, objective as Objective, target_value as Target FROM MISSION_CHALLENGES WHERE mission_id = %s ORDER BY step_number ASC", (m['mission_id'],))
                
                if challs:
                    df_challs = pd.DataFrame(challs)
                else:
                    df_challs = pd.DataFrame(columns=["challenge_id", "Step", "Question", "Objective", "Target"])
                
                st.markdown("**Edit Challenges (Step-by-Step):**")
                edited_df = st.data_editor(df_challs, column_config={"challenge_id": None}, num_rows="dynamic", use_container_width=True)
                
                save_btn = st.form_submit_button("💾 OVERWRITE MISSION DATA", type="primary", use_container_width=True)
                
            if save_btn:
                orig_ids = [c['challenge_id'] for c in challs]
                current_ids = []
                
                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        # 1. Update Title, Brief, and File
                        if edit_file:
                            file_name = edit_file.name
                            file_data = edit_file.getvalue()
                            cursor.execute("UPDATE MISSION_MASTER SET mission_title = %s, mission_brief = %s, file_name = %s, file_data = %s WHERE mission_id = %s", (edit_title, edit_brief, file_name, file_data, m['mission_id']))
                        else:
                            cursor.execute("UPDATE MISSION_MASTER SET mission_title = %s, mission_brief = %s WHERE mission_id = %s", (edit_title, edit_brief, m['mission_id']))
                        
                        # 2. Update, Insert, or Delete Challenges
                        for _, row in edited_df.iterrows():
                            cid = row.get('challenge_id', None)
                            if pd.notna(cid):
                                cid = int(cid)
                                current_ids.append(cid)
                                cursor.execute("UPDATE MISSION_CHALLENGES SET step_number=%s, question_title=%s, objective=%s, target_value=%s WHERE challenge_id=%s", (row['Step'], row['Question'], row['Objective'], row['Target'], cid))
                            else:
                                cursor.execute("INSERT INTO MISSION_CHALLENGES (mission_id, step_number, question_title, objective, target_value) VALUES (%s, %s, %s, %s, %s)", (m['mission_id'], row['Step'], row['Question'], row['Objective'], row['Target']))
                        
                        # Remove deleted challenges
                        for oid in orig_ids:
                            if oid not in current_ids:
                                cursor.execute("DELETE FROM MISSION_CHALLENGES WHERE challenge_id = %s", (oid,))
                        
                        conn.commit()
                    st.success("Mission successfully updated!")
                    time.sleep(1)
                    st.rerun()
                finally:
                    conn.close()
            
            st.divider()
            if st.button(f"🗑️ Permanently Delete '{m['mission_title']}'", type="secondary"):
                run_query("DELETE FROM MISSION_MASTER WHERE mission_id = %s", (m['mission_id'],), fetch=False)
                st.toast("Mission Deleted from Database.")
                time.sleep(1)
                st.rerun()
                
        else:
            st.info("No missions available. Create one to get started.")

# ==========================================
# 5. GLOBAL DATA FETCH (Syncs Admin and Pods)
# ==========================================
active_mission_data = run_query("SELECT * FROM MISSION_MASTER WHERE is_active = True LIMIT 1")
mission = active_mission_data[0] if active_mission_data else None

is_time_up = False
is_lab_ended = False
timer_end_time = None

if mission:
    timer_end_time = mission['end_time']
    if timer_end_time:
        is_time_up = datetime.now() >= timer_end_time
    is_lab_ended = mission['is_completed'] or is_time_up

# ==========================================
# 6. SIDEBAR: AUTHENTICATION & ADMIN
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3256/3256114.png", width=80)
    st.title("Terminal Access")
    
    with st.expander("⚙️ Admin Console"):
        admin_pass = st.text_input("Admin Password", type="password")
        if admin_pass == "cfo2026":
            st.session_state.admin_mode = True
            st.success("Admin Access Granted")
            
            st.markdown("### 📡 Live Operations")
            missions = run_query("SELECT mission_id, mission_title, is_active FROM MISSION_MASTER ORDER BY created_at DESC")
            
            if missions:
                mission_dict = {f"ID {m['mission_id']}: {m['mission_title']}": m['mission_id'] for m in missions}
                active_m_title = next((f"ID {m['mission_id']}: {m['mission_title']}" for m in missions if m['is_active']), None)
                
                selected_mission = st.selectbox("Select Mission to Broadcast", options=list(mission_dict.keys()), index=list(mission_dict.keys()).index(active_m_title) if active_m_title else 0)
                
                if st.button("🔴 ACTIVATE SELECTED MISSION", use_container_width=True):
                    run_query("UPDATE MISSION_MASTER SET is_active = False, end_time = NULL, is_completed = False", fetch=False)
                    run_query("UPDATE MISSION_MASTER SET is_active = True WHERE mission_id = %s", (mission_dict[selected_mission],), fetch=False)
                    st.success(f"Mission is now live!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("No missions found in database.")
                
            if st.button("➕ Open Mission Studio", use_container_width=True):
                mission_studio()
            
            st.divider()
            
            if mission:
                st.markdown("### ⏱️ Master Mission Controls")
                col1, col2 = st.columns(2)
                timer_mins = col1.number_input("Set Timer (Mins)", min_value=1, value=15)
                
                if col2.button("▶️ START TIMER", use_container_width=True):
                    new_end_time = datetime.now() + timedelta(minutes=timer_mins)
                    run_query("UPDATE MISSION_MASTER SET end_time = %s, is_completed = False WHERE mission_id = %s", (new_end_time, mission['mission_id']), fetch=False)
                    st.success("Global Timer Started!")
                    time.sleep(1)
                    st.rerun()
                
                if st.button("🏁 HALT TRADING (Reveal Podium)", type="primary", use_container_width=True):
                    run_query("UPDATE MISSION_MASTER SET is_completed = True WHERE mission_id = %s", (mission['mission_id'],), fetch=False)
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("Activate a mission to access timer controls.")
            
        elif admin_pass:
            st.error("Invalid Admin Password")

    st.divider()

    if not st.session_state.logged_in:
        st.subheader("Pod Authentication")
        pod_select = st.selectbox("Select Pod", list(range(1, 14)))
        pod_pass = st.text_input("Pod Password", type="password")
        
        if st.button("LOGIN"):
            user_data = run_query("SELECT * FROM POD_AUTH WHERE pod_number = %s AND pod_password = %s", (pod_select, pod_pass))
            if user_data:
                st.session_state.logged_in = True
                st.session_state.pod_num = pod_select
                st.session_state.team_name = user_data[0]['team_name']
                st.rerun()
            else:
                st.error("Invalid Credentials.")
    else:
        st.success(f"Connected to Pod {st.session_state.pod_num}")
        if st.button("LOGOUT"):
            for key in ['logged_in', 'pod_num', 'team_name']:
                st.session_state[key] = None
            st.rerun()

# ==========================================
# 7. MAIN DASHBOARD & GAMIFIED MISSION LOGIC
# ==========================================
st.markdown("<div class='main-header'>Fintech Speed Lab</div>", unsafe_allow_html=True)

if timer_end_time and not is_lab_ended:
    time_remaining = (timer_end_time - datetime.now()).total_seconds()
    mins, secs = divmod(int(time_remaining), 60)
    st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>⏳ TIME REMAINING: {mins:02d}:{secs:02d}</h2>", unsafe_allow_html=True)
elif is_lab_ended:
    st.markdown("<h2 style='text-align: center; color: #FF4B4B;'>🛑 LAB LOCKED - TRADING HALTED</h2>", unsafe_allow_html=True)

if st.session_state.logged_in:
    
    if not st.session_state.team_name:
        st.warning("⚠️ Name our Hedge Fund/Pod to Unlock the Dashboard!")
        new_team_name = st.text_input("Enter our official Team/Fund Name:")
        if st.button("🚀 Lock In Team Name"):
            if len(new_team_name.strip()) > 2:
                run_query("UPDATE POD_AUTH SET team_name = %s WHERE pod_number = %s", (new_team_name.strip(), st.session_state.pod_num), fetch=False)
                st.session_state.team_name = new_team_name.strip()
                st.rerun()
        st.stop()
    
    st.markdown(f"<h3 style='text-align: center;'>🏦 Fund: <b>{st.session_state.team_name}</b></h3>", unsafe_allow_html=True)
    
    if not mission:
        st.info("📡 Standing by. Awaiting CFO to deploy the next mission...")
    else:
        m_id = mission['mission_id']
        
        with st.expander("📜 VIEW CFO MISSION BRIEF", expanded=False):
            st.markdown(f"### {mission['mission_title']}")
            st.markdown(mission['mission_brief'])
            if mission['file_data']:
                st.divider()
                st.download_button(
                    label=f"📥 ACQUIRE DATASET: {mission['file_name']}",
                    data=mission['file_data'],
                    file_name=mission['file_name'],
                    use_container_width=True
                )

        st.divider()
        
        challenges = run_query("SELECT * FROM MISSION_CHALLENGES WHERE mission_id = %s ORDER BY step_number ASC", (m_id,))
        total_challenges = len(challenges)
        
        progress_data = run_query("SELECT challenge_id FROM CHALLENGE_SUBMISSIONS WHERE pod_number = %s AND mission_id = %s AND is_correct = True", (st.session_state.pod_num, m_id))
        solved_ids = [p['challenge_id'] for p in progress_data] if progress_data else []
        
        current_step_num = 1
        for c in challenges:
            if c['challenge_id'] in solved_ids:
                current_step_num = c['step_number'] + 1
        
        completion_pct = int((len(solved_ids) / total_challenges) * 100) if total_challenges > 0 else 0
        st.markdown(f"### 🎯 Active Operations Status: {completion_pct}%")
        st.progress(completion_pct / 100)
        
        if current_step_num > total_challenges:
            if not is_lab_ended:
                st.balloons()
            st.success("🏆 ALL MISSIONS ACCOMPLISHED! Alpha Generated. The Board is extremely pleased.")
            
        for c in challenges:
            step = c['step_number']
            
            if step < current_step_num:
                st.markdown(f"<div class='challenge-card'><h4>✅ Phase {step} Secured: {c['question_title']}</h4></div>", unsafe_allow_html=True)
            
            elif step == current_step_num:
                st.markdown(f"""
                <div class='challenge-card' style='border-color: #00FFAA; border-width: 2px;'>
                    <h4>▶️ Phase {step}: {c['question_title']}</h4>
                    <p style='color: #8892B0; padding-left: 5px; border-left: 3px solid #FFD700; margin-bottom: 20px;'>
                        <b>Objective:</b> {c['objective']}
                    </p>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    with st.form(key=f"form_step_{step}"):
                        val = st.number_input("Enter Computed Metric:", format="%.2f", disabled=is_lab_ended)
                        
                        audit_code = st.text_area("Audit Trail (Paste your Pandas code here):", 
                                                  placeholder="e.g., df['Revenue'].dropna()...", 
                                                  disabled=is_lab_ended)
                        
                        submit = st.form_submit_button("⚡ EXECUTE TRADE / SUBMIT", disabled=is_lab_ended, use_container_width=True)
                        
                        if submit and not is_lab_ended:
                            if len(audit_code.strip()) < 10:
                                st.toast("❌ Audit Failed. You must provide your Python/Pandas code.", icon="🚨")
                            else:
                                is_correct = bool(abs(val - c['target_value']) <= TOLERANCE)
                                
                                run_query("""
                                    INSERT INTO CHALLENGE_SUBMISSIONS (pod_number, mission_id, challenge_id, submitted_value, is_correct, audit_code) 
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (st.session_state.pod_num, m_id, c['challenge_id'], val, is_correct, audit_code), fetch=False)
                                
                                if is_correct:
                                    st.toast("✅ Metric Validated! Decrypting next phase...", icon="🔓")
                                    time.sleep(1.2)
                                    st.rerun()
                                else:
                                    st.toast("❌ Audit Failed. Recalculate your matrix.", icon="🚨")
                st.markdown("</div>", unsafe_allow_html=True)
            
            else:
                st.markdown(f"<div class='locked-card'><h4>🔒 Phase {step}: Classified (Clear Phase {step-1} to Access)</h4></div>", unsafe_allow_html=True)

st.divider()

# ==========================================
# 8. GAMIFIED LEADERBOARD & PODIUM
# ==========================================
st.markdown("### 🏆 GLOBAL POD LEADERBOARD")

if mission:
    m_id = mission['mission_id']
    total_q = run_query("SELECT COUNT(*) as t FROM MISSION_CHALLENGES WHERE mission_id = %s", (m_id,))[0]['t']
    
    pods_data = run_query("SELECT p.pod_number, COALESCE(p.team_name, 'Unnamed Pod') as team_name, GROUP_CONCAT(DISTINCT s.student_name SEPARATOR ', ') as students FROM POD_AUTH p LEFT JOIN STUDENT_MASTER s ON p.pod_number = s.pod_number GROUP BY p.pod_number, p.team_name")
    subs_data = run_query("SELECT * FROM CHALLENGE_SUBMISSIONS WHERE mission_id = %s ORDER BY submission_time ASC", (m_id,))
    
    df_pods = pd.DataFrame(pods_data)
    
    if subs_data:
        df_subs = pd.DataFrame(subs_data)
        
        BASE_SCORE = 100
        PENALTY_PER_MISS = 15
        SPEED_DEMON_BONUS = 50
        
        scores = []
        
        correct_subs = df_subs[df_subs['is_correct'] == 1]
        first_bloods = correct_subs.drop_duplicates(subset=['challenge_id'], keep='first')
        
        for pod in df_pods['pod_number']:
            pod_subs = df_subs[df_subs['pod_number'] == pod]
            pod_score = 0
            phases_cleared = 0
            badges = []
            
            for c_id in pod_subs['challenge_id'].unique():
                c_attempts = pod_subs[pod_subs['challenge_id'] == c_id]
                if 1 in c_attempts['is_correct'].values:
                    phases_cleared += 1
                    misses = len(c_attempts) - 1
                    
                    points = max(BASE_SCORE - (misses * PENALTY_PER_MISS), 20) 
                    
                    if pod in first_bloods[first_bloods['challenge_id'] == c_id]['pod_number'].values:
                        points += SPEED_DEMON_BONUS
                        badges.append("⚡")
                    
                    pod_score += points
            
            last_act = pod_subs['submission_time'].max() if not pod_subs.empty else pd.NaT
            scores.append({'pod_number': pod, 'Score': pod_score, 'Phases': phases_cleared, 'Last Signal': last_act, 'Badges': "".join(badges)})
            
        df_scores = pd.DataFrame(scores)
        df_master = pd.merge(df_pods, df_scores, on='pod_number', how='left').fillna({'Score': 0, 'Phases': 0, 'Badges': ''})
        
        df_master = df_master.sort_values(by=['Score', 'Last Signal'], ascending=[False, True]).reset_index(drop=True)
        df_master.insert(0, 'Rank', range(1, len(df_master) + 1))
        
        if is_lab_ended:
            st.markdown("<h2 style='text-align: center; color: #FFD700;'>🏁 TRADING HALTED - FINAL RESULTS 🏁</h2>", unsafe_allow_html=True)
            col_2, col_1, col_3 = st.columns([1, 1.2, 1])
            
            if len(df_master) >= 1:
                with col_1:
                    st.markdown(f"<div style='background: #3b2b00; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #FFD700;'><h1 style='margin:0;'>🥇 1ST</h1><h3>{df_master.iloc[0]['team_name']}</h3><h2>{int(df_master.iloc[0]['Score'])} PTS</h2><p style='color: #8892B0;'>{df_master.iloc[0]['students']}</p></div>", unsafe_allow_html=True)
            if len(df_master) >= 2:
                with col_2:
                    st.markdown(f"<div style='background: #161b26; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #C0C0C0; margin-top: 30px;'><h2 style='margin:0;'>🥈 2ND</h2><h4>{df_master.iloc[1]['team_name']}</h4><h3>{int(df_master.iloc[1]['Score'])} PTS</h3></div>", unsafe_allow_html=True)
            if len(df_master) >= 3:
                with col_3:
                    st.markdown(f"<div style='background: #2a1b15; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #CD7F32; margin-top: 50px;'><h3 style='margin:0;'>🥉 3RD</h3><h4>{df_master.iloc[2]['team_name']}</h4><h3>{int(df_master.iloc[2]['Score'])} PTS</h3></div>", unsafe_allow_html=True)
            
            st.divider()
        
        df_display = df_master[['Rank', 'team_name', 'Badges', 'Score', 'Phases']].copy()
        df_display['Phases'] = df_display['Phases'].apply(lambda x: f"{int(x)} / {total_q}")
        df_display = df_display.rename(columns={'team_name': 'Hedge Fund'})
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
    else:
        st.info("Market is quiet. Awaiting first pod transmission...")
else:
    st.info("Leaderboard will populate when a mission is deployed.")
