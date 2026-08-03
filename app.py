import streamlit as st
import pandas as pd
import pymysql                  # <-- Swapped to pure python
import pymysql.cursors          # <-- Added for dictionary support
from datetime import datetime, timedelta
import time

# ==========================================
# 1. APP CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="Speed Lab: Project Reliance", page_icon="⚡", layout="wide")

# Custom CSS for Dark-Mode Trading Desk Aesthetic
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E6ED; }
    .main-header { font-size: 2.5rem; font-weight: 900; color: #00FFAA; text-align: center; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 0px; }
    .sub-header { text-align: center; color: #8892B0; font-size: 1.2rem; margin-bottom: 30px; }
    .status-badge-val { background-color: #173b22; color: #00FFAA; padding: 4px 10px; border-radius: 5px; font-weight: bold; }
    .status-badge-fix { background-color: #4a151b; color: #FF4B4B; padding: 4px 10px; border-radius: 5px; font-weight: bold; }
    .status-badge-prog { background-color: #3b2b00; color: #FFD700; padding: 4px 10px; border-radius: 5px; font-weight: bold; }
    div[data-testid="stMetricValue"] { color: #00FFAA; }
    </style>
""", unsafe_allow_html=True)

# Master Answer Key
ANSWER_KEY = {'Q1': 0.15, 'Q2': 1.25, 'Q3': 1.80}
TOLERANCE = 0.01

# ==========================================
# 2. DATABASE CONNECTION (THREAD-SAFE FIX)
# ==========================================

def run_query(query, params=None, fetch=True):
    # 1. Open a fresh, isolated connection for every query
    conn = pymysql.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
    
    # 2. Execute the query and guarantee the connection closes
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            else:
                return None
    finally:
        # 3. Always close the connection so it doesn't leak memory
        conn.close()

# ==========================================
# 3. SESSION STATE INITIALIZATION
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'pod_num' not in st.session_state:
    st.session_state.pod_num = None
if 'team_name' not in st.session_state:
    st.session_state.team_name = None
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False
if 'timer_end' not in st.session_state:
    st.session_state.timer_end = None

# ==========================================
# 4. SIDEBAR: AUTHENTICATION & ADMIN
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3256/3256114.png", width=80)
    st.title("Terminal Access")
    
    # Admin Panel
    with st.expander("⚙️ Admin Console"):
        admin_pass = st.text_input("Admin Password", type="password")
        if admin_pass == "cfo2026":
            st.session_state.admin_mode = True
            st.success("Admin Access Granted")
            timer_mins = st.number_input("Set Timer (Minutes)", min_value=1, value=15)
            if st.button("▶️ START SPEED LAB"):
                st.session_state.timer_end = datetime.now() + timedelta(minutes=timer_mins)
                st.success(f"Lab Timer started for {timer_mins} minutes!")
        elif admin_pass:
            st.error("Invalid Admin Password")

    st.divider()

    # Pod Login
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
                st.error("Invalid Credentials. Check pod number and password.")
    else:
        st.success(f"Connected to Pod {st.session_state.pod_num}")
        if st.button("LOGOUT"):
            st.session_state.logged_in = False
            st.session_state.pod_num = None
            st.session_state.team_name = None
            st.rerun()

# ==========================================
# 5. TIMER MANAGEMENT
# ==========================================
time_remaining = 0
is_locked = False

if st.session_state.timer_end:
    now = datetime.now()
    if now < st.session_state.timer_end:
        time_remaining = (st.session_state.timer_end - now).total_seconds()
        mins, secs = divmod(int(time_remaining), 60)
        st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>⏳ TIME REMAINING: {mins:02d}:{secs:02d}</h2>", unsafe_allow_html=True)
    else:
        is_locked = True
        st.markdown("<h2 style='text-align: center; color: #FF4B4B;'>🛑 LAB LOCKED - TIME IS UP</h2>", unsafe_allow_html=True)

# ==========================================
# 6. MAIN DASHBOARD & LOGIC
# ==========================================
st.markdown("<div class='main-header'>Project Reliance Cleanup</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>CFO Operations Dashboard // Alpha Release v1.0</div>", unsafe_allow_html=True)

if st.session_state.logged_in:
    
    # --- FETCH TEAM MEMBERS ---
    students = run_query("SELECT student_name FROM STUDENT_MASTER WHERE pod_number = %s", (st.session_state.pod_num,))
    student_names = ", ".join([s['student_name'] for s in students]) if students else "No members mapped yet."
    st.info(f"👨‍💻 **Pod Roster:** {student_names}")

    # --- TEAM NAME SETUP ---
    if not st.session_state.team_name:
        st.warning("⚠️ Name Your Hedge Fund/Pod to Unlock Submission!")
        col1, col2 = st.columns([3, 1])
        new_team_name = col1.text_input("Enter your official Team/Fund Name:")
        if col2.button("🚀 Lock In Team Name", use_container_width=True):
            if len(new_team_name.strip()) > 2:
                run_query("UPDATE POD_AUTH SET team_name = %s WHERE pod_number = %s", (new_team_name.strip(), st.session_state.pod_num), fetch=False)
                st.session_state.team_name = new_team_name.strip()
                st.rerun()
            else:
                st.error("Name must be at least 3 characters.")
        
        st.stop() # Halts rendering until team name is set
    
    st.markdown(f"### 🏦 Fund: **{st.session_state.team_name}**")

    # --- CFO MISSION BRIEF ---
    with st.expander("📜 VIEW CFO MISSION BRIEF & DATA PARAMS"):
        st.markdown("""
        **To:** All Incoming Financial Analytics Pods  
        **From:** Office of the Chief Financial Officer  
        
        Our automated data feed from the exchange corrupted the financial dump for Reliance Industries (`Reliance_Financials_Corrupted.csv`). 
        
        **YOUR MISSIONS:**
        1. **Profitability (Q1):** Drop rows where `Revenue` is `NaN`. Calculate **Net Profit Margin** (Net Income / Revenue).
        2. **Leverage (Q2):** Clean the `Total Debt` column (remove `$` and `,`, cast to float). Calculate **Debt-to-Equity Ratio** (Total Debt / Total Equity).
        3. **Liquidity (Q3):** Use EDA to find and drop the fat-finger outlier in `Current Liabilities`. Calculate **Current Ratio** (Current Assets / Current Liabilities).
        """)

    st.divider()

    # --- SUBMISSION PORTAL ---
    st.markdown("### ⚡ METRICS INGRESS PORTAL")
    
    with st.form("submission_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            q1_val = st.number_input("M1: Net Profit Margin (Q1)", format="%.2f", disabled=is_locked)
        with col2:
            q2_val = st.number_input("M2: Debt-to-Equity (Q2)", format="%.2f", disabled=is_locked)
        with col3:
            q3_val = st.number_input("M3: Current Ratio (Q3)", format="%.2f", disabled=is_locked)
            
        submitted = st.form_submit_button("⚡ SUBMIT METRICS", disabled=is_locked, use_container_width=True)
        
        if submitted and not is_locked:
            # Evaluate Score
            score = 0
            if abs(q1_val - ANSWER_KEY['Q1']) <= TOLERANCE: score += 1
            if abs(q2_val - ANSWER_KEY['Q2']) <= TOLERANCE: score += 1
            if abs(q3_val - ANSWER_KEY['Q3']) <= TOLERANCE: score += 1
            
            # Ingress to DB
            run_query("""
                INSERT INTO LAB_SUBMISSIONS (pod_number, session_id, q1_answer, q2_answer, q3_answer) 
                VALUES (%s, 'DAY2_LAB1', %s, %s, %s)
            """, (st.session_state.pod_num, q1_val, q2_val, q3_val), fetch=False)
            
            if score == 3:
                st.balloons()
                st.success("🎯 FLAWLESS SUBMISSION! 3/3 Validated! The Board is pleased.")
            else:
                st.warning(f"Submission accepted. {score}/3 metrics validated. Check the Leaderboard and adjust your code!")
            time.sleep(1.5)
            st.rerun()

st.divider()

# ==========================================
# 7. HIGH-ENERGY LEADERBOARD
# ==========================================
st.markdown("### 🏆 GLOBAL POD LEADERBOARD")

# Helper function to evaluate status
def get_status_html(val, target):
    if pd.isna(val):
        return "<span class='status-badge-prog'>In Progress ⏳</span>"
    if abs(float(val) - target) <= TOLERANCE:
        return "<span class='status-badge-val'>Validated ✅</span>"
    return "<span class='status-badge-fix'>Needs Fix ❌</span>"

# Fetch Master Data
pods_df = pd.DataFrame(run_query("SELECT pod_number, team_name FROM POD_AUTH"))
students_df = pd.DataFrame(run_query("SELECT pod_number, student_name FROM STUDENT_MASTER"))
subs_df = pd.DataFrame(run_query("SELECT pod_number, q1_answer, q2_answer, q3_answer, submission_time FROM LAB_SUBMISSIONS"))

if not pods_df.empty:
    # Aggregate Students
    if not students_df.empty:
        students_grouped = students_df.groupby('pod_number')['student_name'].apply(lambda x: ', '.join(x)).reset_index()
    else:
        students_grouped = pd.DataFrame(columns=['pod_number', 'student_name'])

    # Aggregate Submissions
    if not subs_df.empty:
        subs_df['submission_time'] = pd.to_datetime(subs_df['submission_time'])
        
        # Get attempt count
        attempts = subs_df.groupby('pod_number').size().reset_index(name='Attempts')
        
        # Get latest submission
        latest_subs = subs_df.sort_values('submission_time').groupby('pod_number').tail(1)
        
        # Merge stats
        lab_stats = pd.merge(latest_subs, attempts, on='pod_number')
    else:
        lab_stats = pd.DataFrame(columns=['pod_number', 'q1_answer', 'q2_answer', 'q3_answer', 'submission_time', 'Attempts'])

    # Build Master Leaderboard DataFrame
    lb_df = pd.merge(pods_df, students_grouped, on='pod_number', how='left')
    lb_df = pd.merge(lb_df, lab_stats, on='pod_number', how='left')
    
    # Clean up display names
    lb_df['team_name'] = lb_df['team_name'].fillna('Unnamed Pod')
    lb_df['student_name'] = lb_df['student_name'].fillna('Pending Roster')
    
    # Calculate Scores & Statuses
    lb_df['Q1 Status'] = lb_df['q1_answer'].apply(lambda x: get_status_html(x, ANSWER_KEY['Q1']))
    lb_df['Q2 Status'] = lb_df['q2_answer'].apply(lambda x: get_status_html(x, ANSWER_KEY['Q2']))
    lb_df['Q3 Status'] = lb_df['q3_answer'].apply(lambda x: get_status_html(x, ANSWER_KEY['Q3']))
    
    lb_df['Total Score'] = (
        (abs(lb_df['q1_answer'] - ANSWER_KEY['Q1']) <= TOLERANCE).astype(int) +
        (abs(lb_df['q2_answer'] - ANSWER_KEY['Q2']) <= TOLERANCE).astype(int) +
        (abs(lb_df['q3_answer'] - ANSWER_KEY['Q3']) <= TOLERANCE).astype(int)
    )
    
    # Sorting: Total Score (DESC) -> Timestamp (ASC) -> Attempts (ASC)
    lb_df['submission_time'] = lb_df['submission_time'].fillna(pd.Timestamp('2099-01-01'))
    lb_df = lb_df.sort_values(by=['Total Score', 'submission_time', 'Attempts'], ascending=[False, True, True])
    lb_df['submission_time'] = lb_df['submission_time'].replace(pd.Timestamp('2099-01-01'), pd.NaT)
    
    # Create rank column
    lb_df.insert(0, 'Rank', range(1, len(lb_df) + 1))
    
    # Format Output Table
    display_cols = {
        'Rank': 'Rank', 
        'pod_number': 'Pod #', 
        'team_name': 'Team Name',
        'student_name': 'Team Members', 
        'Q1 Status': 'Q1: Profitability', 
        'Q2 Status': 'Q2: Leverage', 
        'Q3 Status': 'Q3: Liquidity', 
        'Total Score': 'Score', 
        'Attempts': 'Attempts'
    }
    
    final_df = lb_df[display_cols.keys()].rename(columns=display_cols)
    final_df['Attempts'] = final_df['Attempts'].fillna(0).astype(int)
    
    # Render with HTML to support the custom status badges
    html_table = final_df.to_html(escape=False, index=False, classes='stTable')
    st.markdown(html_table, unsafe_allow_html=True)

else:
    st.info("Awaiting seed data initialization.")
