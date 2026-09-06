import streamlit as st
import pandas as pd
import json, re, random, sys, requests, time, io
from ortools.sat.python import cp_model

st.set_page_config(page_title="Advanced Timetable Pro (OR-Tools + AI Studio)", layout="wide")

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🔑 API Keys Setup")
    st.markdown("### Architecture:\n- **AI-1**: Chat Collector\n- **AI-2**: Data & JSON Sync\n- **AI-RuleBridge**: Text to OR-Tools Constraints\n- **Engine**: Google OR-Tools CP-SAT")
    nvidia_api_key = st.text_input("Nvidia Master Key (nvapi-...)", type="password")
    st.info("🛡️ Bina quotes ke API key dalein.")

# ================= AI HELPER =================
def call_nvidia(messages, temp=0.1, max_tokens=4000):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tokens
    }
    res = requests.post(url, headers=headers, json=payload, timeout=320)
    if res.status_code != 200:
        raise Exception(f"Nvidia API Error: {res.text}")
    return res.json()["choices"][0]["message"]["content"]

# ================= ROBUST JSON PARSER =================
def extract_json_safe(raw_text):
    if not raw_text:
        return None
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    s_idx = raw_text.find("{")
    e_idx = raw_text.rfind("}")
    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
        raw = raw_text[s_idx:e_idx+1]
        raw = re.sub(r',\s*}', '}', raw)
        raw = re.sub(r',\s*]', ']', raw)
        try:
            return json.loads(raw)
        except Exception:
            pass
    return None

def parse_allowed_classes(allowed_str, all_classes):
    s = str(allowed_str).strip()
    if not s or s.lower() == "all":
        return list(all_classes)
    tokens = [x.strip().lower() for x in s.split(",")]
    return [c for c in all_classes if c.lower() in tokens]

# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 7
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "saturday_half_day" not in st.session_state: st.session_state.saturday_half_day = False

if "classes_df" not in st.session_state: 
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["9-A", "9-B", "10-A", "10-B"]})

if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame([
        {"Teacher Name": "Amit Sharma", "Subject": "Mathematics", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Deeksha Pawar", "Subject": "Science", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Ravi Joshi", "Subject": "English", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Priya Yadav", "Subject": "Social Science", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Vikram Singh", "Subject": "Hindi", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Karan Malhotra", "Subject": "Computer", "Allowed Classes": "all", "Periods/Week (Per Class)": 3},
        {"Teacher Name": "Nisha Patel", "Subject": "Library", "Allowed Classes": "all", "Periods/Week (Per Class)": 3}
    ])

# Structured Day-by-Day Rules Matrix
if "day_rules_df" not in st.session_state:
    st.session_state.day_rules_df = pd.DataFrame([
        {"Day": "Monday", "Rule Type": "ASSEMBLY_SLOT", "Target": "All", "Value": "1", "Status": "Active"},
        {"Day": "Tuesday", "Rule Type": "TEACHER_LEAVE", "Target": "Deeksha Pawar", "Value": "", "Status": "Active"},
        {"Day": "Wednesday", "Rule Type": "DOUBLE_PERIOD_LAB", "Target": "Science", "Value": "10-A", "Status": "Active"},
        {"Day": "All", "Rule Type": "MAX_CONSECUTIVE", "Target": "All Teachers", "Value": "3", "Status": "Active"}
    ])

if "rules_df" not in st.session_state: 
    st.session_state.rules_df = pd.DataFrame({"Rule": [
        "Monday Period 1 is Morning Assembly for all classes.",
        "Deeksha Mam is on leave on Tuesday.",
        "No teacher should teach more than 3 consecutive periods.",
        "Core subjects daily minimum 1 period."
    ]})

if "chat_messages" not in st.session_state: st.session_state.chat_messages = []
if "single_day_schedule" not in st.session_state: st.session_state.single_day_schedule = None
if "weekly_schedule" not in st.session_state: st.session_state.weekly_schedule = None

# ================= OR-TOOLS ENGINE SOLVER =================
def solve_day_with_ortools(target_day, classes, p_count, break_p, teachers_dict, active_rules, allow_proxies=True):
    model = cp_model.CpModel()
    
    # 1. Process rules for this day
    absent_teachers = set()
    assembly_periods = set()
    max_consecutive = 3
    fixed_slots = {}
    
    for _, r in active_rules.iterrows():
        status = str(r.get("Status", "Active")).strip().lower()
        if status != "active":
            continue
        day_scope = str(r.get("Day", "All")).strip()
        if day_scope not in ["All", target_day]:
            continue
            
        rtype = str(r.get("Rule Type", "")).strip().upper()
        target = str(r.get("Target", "")).strip()
        val = str(r.get("Value", "")).strip()
        
        if rtype == "TEACHER_LEAVE":
            absent_teachers.add(target)
        elif rtype == "ASSEMBLY_SLOT":
            try: assembly_periods.add(int(val))
            except: assembly_periods.add(1)
        elif rtype == "MAX_CONSECUTIVE":
            try: max_consecutive = int(val)
            except: pass
        elif rtype == "FIXED_SLOT":
            # format in val: "Period:Teacher:Subject"
            parts = val.split(":")
            if len(parts) >= 3:
                fixed_slots[(target, int(parts[0]))] = (parts[1], parts[2])

    active_teachers = [t for t in teachers_dict if t not in absent_teachers]
    all_periods = list(range(1, p_count + 1))
    class_periods = [p for p in all_periods if p != break_p and p not in assembly_periods]

    # Variables
    assign = {}
    proxy = {}
    for c in classes:
        for p in class_periods:
            for t in active_teachers:
                assign[(c, p, t)] = model.NewBoolVar(f"a_{c}_{p}_{t}")
            proxy[(c, p)] = model.NewBoolVar(f"pr_{c}_{p}")
            
            # Constraint 1: Exactly one assignment per slot
            if allow_proxies:
                model.Add(sum(assign[(c, p, t)] for t in active_teachers) + proxy[(c, p)] == 1)
            else:
                model.Add(sum(assign[(c, p, t)] for t in active_teachers) == 1)
                model.Add(proxy[(c, p)] == 0)

    # Constraint 2: Teacher Uniqueness (No double booking)
    for p in class_periods:
        for t in active_teachers:
            model.Add(sum(assign[(c, p, t)] for c in classes) <= 1)

    # Constraint 3: Max consecutive periods per teacher
    for t in active_teachers:
        for i in range(len(class_periods) - max_consecutive):
            win = class_periods[i : i + max_consecutive + 1]
            model.Add(sum(assign[(c, p, t)] for c in classes for p in win) <= max_consecutive)

    # Constraint 4: Fixed Slots
    for (f_class, f_p), (f_t, _) in fixed_slots.items():
        if f_class in classes and f_p in class_periods and f_t in active_teachers:
            model.Add(assign[(f_class, f_p, f_t)] == 1)

    # Objective: Minimize proxies and balance workload
    obj = [proxy[(c, p)] * 100 for c in classes for p in class_periods]
    model.Minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return None, solver.StatusName(status), list(absent_teachers)

    # Build result timetable dict
    result_tt = {c: {} for c in classes}
    for c in classes:
        for p in all_periods:
            if p == break_p:
                result_tt[c][f"P{p}"] = "☕ LUNCH / BREAK"
            elif p in assembly_periods:
                result_tt[c][f"P{p}"] = "🔔 Morning Assembly"
            elif solver.Value(proxy[(c, p)]) == 1:
                result_tt[c][f"P{p}"] = "📌 Proxy / Activity"
            else:
                assigned_t = "-"
                for t in active_teachers:
                    if solver.Value(assign[(c, p, t)]) == 1:
                        assigned_t = t
                        break
                subj = teachers_dict.get(assigned_t, "Subject")
                result_tt[c][f"P{p}"] = f"{subj} ({assigned_t})"

    return result_tt, solver.StatusName(status), list(absent_teachers)

# ================= APP UI =================
st.title("🏫 Advanced Timetable Pro (OR-Tools + AI Studio)")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🕒 Timings", "🏫 Classes", "👨‍🏫 Teachers", "⚙️ Rules", "📅 Manual & Day-by-Day Studio", "🚀💬 AI Center"
])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.working_days = st.number_input("Working Days", 1, 7, int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("Periods per Day", 1, 15, int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch Break AFTER period?", 1, 15, int(st.session_state.break_at))
        st.session_state.saturday_half_day = st.checkbox("Saturday Half-Day?", value=st.session_state.saturday_half_day)
    with col2:
        st.info("💡 Tip: Standard school setup 6 working days, 7 periods, Lunch after period 4.")

with tab2:
    st.subheader("Classes / Sections")
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.subheader("Faculty & Subject Allocation")
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.subheader("Plain Text Rules (AI Input)")
    st.session_state.rules_df = st.data_editor(st.session_state.rules_df, num_rows="dynamic", use_container_width=True)
    if st.button("🤖 AI-RuleBridge: Convert Plain Rules to OR-Tools Matrix", use_container_width=True):
        if not nvidia_api_key:
            st.error("❌ Nvidia API Key Missing in Sidebar!")
        else:
            with st.spinner("AI-RuleBridge converting text rules to OR-Tools constraints..."):
                try:
                    plain_rules = st.session_state.rules_df["Rule"].tolist()
                    sys_p = (
                        "You are an Operations Research Rule Compiler. Convert natural language rules into a JSON array of structured constraints for OR-Tools:\n"
                        "[{\"Day\": \"Monday\"|\"Tuesday\"|...|\"All\", \"Rule Type\": \"TEACHER_LEAVE\"|\"ASSEMBLY_SLOT\"|\"DOUBLE_PERIOD_LAB\"|\"MAX_CONSECUTIVE\"|\"FIXED_SLOT\", \"Target\": \"Name\", \"Value\": \"Val\", \"Status\": \"Active\"}]\n"
                        "Output ONLY raw JSON."
                    )
                    reply = call_nvidia([{"role": "system", "content": sys_p}, {"role": "user", "content": json.dumps(plain_rules)}])
                    data = extract_json_safe(reply)
                    if data and isinstance(data, list):
                        st.session_state.day_rules_df = pd.DataFrame(data)
                        st.success("✅ Rules successfully bridged to OR-Tools Matrix! Check 'Manual & Day-by-Day Studio'.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Rule Bridge Error: {e}")

# ================= TAB 5: MANUAL & DAY-BY-DAY STUDIO =================
with tab5:
    st.header("📅 Manual & Day-by-Day Timetable Studio")
    st.markdown("Yahan aap data manually upload/edit kar sakte hain, pehle **Single Day test run** kar sakte hain, aur fir din-ke-hisab se rules lagakar pura week generate kar sakte hain.")

    # Excel / CSV Uploader
    uploaded_file = st.file_uploader("📂 Upload Excel / CSV file (Classes, Teachers, Rules)", type=["xlsx", "csv"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".xlsx"):
                xls = pd.ExcelFile(uploaded_file)
                if "Classes" in xls.sheet_names: st.session_state.classes_df = pd.read_excel(xls, "Classes")
                if "Teachers" in xls.sheet_names: st.session_state.teachers_df = pd.read_excel(xls, "Teachers")
                if "Rules" in xls.sheet_names: st.session_state.day_rules_df = pd.read_excel(xls, "Rules")
                st.success("✅ Excel sheets loaded into tables!")
            else:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df.head())
        except Exception as e:
            st.error(f"Upload error: {e}")

    st.markdown("---")
    st.subheader("1. Day-by-Day Custom Rules Matrix")
    st.markdown("Set specific rules for specific days (e.g., Monday Assembly, Tuesday Leave):")
    st.session_state.day_rules_df = st.data_editor(st.session_state.day_rules_df, num_rows="dynamic", use_container_width=True)

    st.markdown("---")
    col_day1, col_week = st.columns(2, gap="large")

    # STEP 1: SINGLE DAY GENERATOR
    with col_day1:
        st.subheader("2. ⚡ Single Day Test Run")
        st.caption("Pehle 1 din generate karke dekhein ki OR-Tools rules theek se follow kar raha hai ya nahi.")
        selected_day = st.selectbox("Select Target Day:", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
        
        if st.button(f"Generate {selected_day} (Single Day Test)", type="primary", use_container_width=True):
            classes = st.session_state.classes_df["Class Name"].dropna().tolist()
            teachers_dict = {row["Teacher Name"]: row["Subject"] for _, row in st.session_state.teachers_df.iterrows()}
            p_count = int(st.session_state.periods_per_day)
            break_p = int(st.session_state.break_at)
            
            with st.spinner(f"Solving {selected_day} using Google OR-Tools CP-SAT..."):
                res, status_str, absent = solve_day_with_ortools(
                    selected_day, classes, p_count, break_p, teachers_dict, st.session_state.day_rules_df
                )
                if res:
                    st.success(f"🎉 {selected_day} Timetable Generated! (Status: {status_str})")
                    if absent: st.warning(f"🏖️ Teachers on Leave: {', '.join(absent)}")
                    df_day = pd.DataFrame(res).T
                    df_day.index.name = "Class / Section"
                    st.dataframe(df_day, use_container_width=True)
                    st.session_state.single_day_schedule = df_day
                else:
                    st.error(f"❌ OR-Tools Infeasible: {status_str}. Rules ko adjust karein.")

    # STEP 2: FULL WEEK GENERATOR
    with col_week:
        st.subheader("3. 🚀 Full Week Generator")
        st.caption("Single day verify hone ke baad pure week ka timetable generate karein.")
        days_to_run = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][:int(st.session_state.working_days)]
        
        if st.button("Generate Full Week Timetable", type="secondary", use_container_width=True):
            classes = st.session_state.classes_df["Class Name"].dropna().tolist()
            teachers_dict = {row["Teacher Name"]: row["Subject"] for _, row in st.session_state.teachers_df.iterrows()}
            p_count = int(st.session_state.periods_per_day)
            break_p = int(st.session_state.break_at)
            
            all_week_data = []
            success = True
            with st.spinner("Generating full week with Google OR-Tools..."):
                for d in days_to_run:
                    cur_p_count = 4 if (d.lower() == "saturday" and st.session_state.saturday_half_day) else p_count
                    res, status_str, _ = solve_day_with_ortools(
                        d, classes, cur_p_count, break_p, teachers_dict, st.session_state.day_rules_df
                    )
                    if res:
                        df_d = pd.DataFrame(res).T
                        df_d.insert(0, "Day", d)
                        all_week_data.append(df_d)
                    else:
                        st.error(f"❌ {d} failed to solve. Status: {status_str}")
                        success = False
                        break
                        
                if success and all_week_data:
                    final_week_df = pd.concat(all_week_data)
                    st.success("🎉 Full Week Timetable Successfully Generated with Zero Clashes!")
                    st.dataframe(final_week_df, use_container_width=True)
                    st.session_state.weekly_schedule = final_week_df
                    
                    csv = final_week_df.to_csv().encode('utf-8')
                    st.download_button("📥 Download Weekly Timetable (CSV)", csv, "weekly_timetable.csv", "text/csv")

# ================= TAB 6: AI CENTER =================
with tab6:
    st.subheader("💬 AI Chat Data Collector & Sync")
    chat_box = st.container(height=250)
    with chat_box:
        for m in st.session_state.chat_messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
    user_text = st.text_area("Paste Raw School Information Here:", height=80)
    if st.button("Send to AI-1 🚀", use_container_width=True) and user_text:
        st.session_state.chat_messages.append({"role": "user", "content": user_text})
        st.rerun()
