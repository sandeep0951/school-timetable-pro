import streamlit as st
import pandas as pd
import json, re, random, sys, requests, time
from ortools.sat.python import cp_model

st.set_page_config(page_title="Advanced Timetable Pro (Triple AI System)", layout="wide")

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🔑 API Keys Setup")
    st.markdown("Triple AI Architecture:\n1. Chat Collector: DeepSeek V4\n2. JSON Sync: DeepSeek V4\n3. Rule Fixer: DeepSeek V4")
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

# ================= RANGE PARSER =================
def parse_allowed_classes(allowed_str, all_classes):
    s = str(allowed_str).strip()
    if not s or s.lower() == "all":
        return list(all_classes)
    range_match = re.search(r'(\d+)\s*[-_]?\s*([A-Za-z])\s*(?:to|-)\s*(\d+)\s*[-_]?\s*([A-Za-z])', s, re.IGNORECASE)
    if range_match:
        sg = int(range_match.group(1))
        eg = int(range_match.group(3))
        matched = [c for c in all_classes if re.match(r'(\d+)', c) and sg <= int(re.match(r'(\d+)', c).group(1)) <= eg]
        if matched:
            return matched
    tokens = [x.strip().lower() for x in s.split(",")]
    return [c for c in all_classes if c.lower() in tokens]

# ================= CORE SUBJECT IDENTIFIER =================
def is_core_subject(subject_name):
    s = str(subject_name).lower().strip()
    core_keywords = ["math", "science", "social", "hindi", "english", "evs", "sst", "physics", "chemistry", "biology"]
    return any(k in s for k in core_keywords)

# ================= DATA PREPARATION =================
def prepare_engine_data():
    sys.setrecursionlimit(5000)
    classes_list = st.session_state.classes_df["Class Name"].dropna().tolist()
    teachers_list = st.session_state.teachers_df.to_dict("records")
    w_days = int(st.session_state.working_days)
    p_per_day = int(st.session_state.periods_per_day)
    break_at = int(st.session_state.break_at)
    is_half = st.session_state.saturday_half_day

    days_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][:w_days]
    period_labels = []
    valid_periods = []
    global_p_idx = 0

    for d in days_str:
        current_day_periods = 4 if (d.lower() == "saturday" and is_half) else p_per_day
        for p in range(1, current_day_periods + 1):
            global_p_idx += 1
            period_labels.append(f"{d} - P{p}")
            valid_periods.append(global_p_idx)
            if p == break_at and not (d.lower() == "saturday" and is_half):
                period_labels.append(f"{d} - LUNCH")

    total_weekly_periods = len(valid_periods)
    initial_timetable = {c: ["EMPTY"] * len(period_labels) for c in classes_list}
    for c in classes_list:
        for idx, label in enumerate(period_labels):
            if "LUNCH" in label:
                initial_timetable[c][idx] = "LUNCH / BREAK"

    # Group teachers by subject to balance workload and prevent deadlocks
    subjects_map = {}
    for t in teachers_list:
        sub = str(t.get("Subject", "")).strip()
        if not sub:
            continue
        try:
            p_count = int(t.get("Periods/Week (Per Class)", 4))
        except Exception:
            p_count = 4
        if sub not in subjects_map:
            subjects_map[sub] = {"periods": p_count, "teachers": []}
        subjects_map[sub]["teachers"].append({
            "name": t.get("Teacher Name", ""),
            "allowed": parse_allowed_classes(t.get("Allowed Classes", ""), classes_list),
            "load": 0
        })

    class_requirements = {c: [] for c in classes_list}
    for sub, info in subjects_map.items():
        p_count = info["periods"]
        teachers = info["teachers"]
        for c in classes_list:
            eligible = [t for t in teachers if c in t["allowed"]]
            if not eligible:
                continue
            eligible.sort(key=lambda x: x["load"])
            chosen = eligible[0]
            chosen["load"] += p_count
            for _ in range(p_count):
                class_requirements[c].append((chosen["name"], sub))

    for c in classes_list:
        while len(class_requirements[c]) < total_weekly_periods:
            class_requirements[c].append(("-", "Free Period"))
        if len(class_requirements[c]) > total_weekly_periods:
            class_requirements[c] = class_requirements[c][:total_weekly_periods]

    return classes_list, period_labels, valid_periods, initial_timetable, class_requirements

# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 7
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "saturday_half_day" not in st.session_state: st.session_state.saturday_half_day = False
if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 45} for i in range(1, 8)]
    slots.insert(4, {"Slot": "LUNCH BREAK", "Duration (Mins)": 30})
    st.session_state.periods_timing_df = pd.DataFrame(slots)
if "classes_df" not in st.session_state: 
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["1-A", "1-B"]})
if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame([
        {"Teacher Name": "Amit Sharma", "Subject": "English", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Rahul Jain", "Subject": "Mathematics", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Rajesh Singh", "Subject": "Hindi", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Kavita Joshi", "Subject": "Science", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Rakesh Gupta", "Subject": "Social Science", "Allowed Classes": "all", "Periods/Week (Per Class)": 6},
        {"Teacher Name": "Karan Malhotra", "Subject": "Computer", "Allowed Classes": "all", "Periods/Week (Per Class)": 3},
        {"Teacher Name": "Priyanka Yadav", "Subject": "Art & Craft", "Allowed Classes": "all", "Periods/Week (Per Class)": 3},
        {"Teacher Name": "Ravi Joshi", "Subject": "Physical Education", "Allowed Classes": "all", "Periods/Week (Per Class)": 3},
        {"Teacher Name": "Nisha Patel", "Subject": "Library", "Allowed Classes": "all", "Periods/Week (Per Class)": 3}
    ])
if "rules_df" not in st.session_state: 
    st.session_state.rules_df = pd.DataFrame({"Rule": [
        "Core subjects (Maths, Science, SST, Hindi, English) daily minimum 1 period.",
        "Other activities (Computer, Sports, Library, Art) different days par rotate hon.",
        "No teacher conflict and no consecutive same subjects."
    ]})
if "chat_messages" not in st.session_state: st.session_state.chat_messages = []

st.title("🏫 Advanced Timetable Pro (Triple AI System)")

# ================= UI TABS =================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🕒 Timings", "🏫 Classes", "👨‍🏫 Teachers", "⚙️ Rules", "🚀💬 AI & Engine Center"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.working_days = st.number_input("1. Working Days", 1, 7, int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("2. Periods per Day", 1, 20, int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch Break AFTER period?", 1, 15, int(st.session_state.break_at))
        st.session_state.saturday_half_day = st.checkbox("4. Saturday Half-Day?", value=st.session_state.saturday_half_day)
    with col2:
        st.session_state.periods_timing_df = st.data_editor(st.session_state.periods_timing_df, use_container_width=True, hide_index=True)

with tab2:
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.session_state.rules_df = st.data_editor(st.session_state.rules_df, num_rows="dynamic", use_container_width=True)

with tab5:
    st.markdown("### 🛠️ Step 1 & 2: Setup Data & Run Engine")
    col_chat, col_engine = st.columns([4, 6], gap="large")

    with col_chat:
        st.subheader("💬 AI-1 Data Collector")
        chat_box = st.container(height=250)
        with chat_box:
            for m in st.session_state.chat_messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

        with st.form("chat_form", clear_on_submit=True):
            user_text = st.text_area("Paste Data Here:", height=80)
            btn_c1, btn_c2 = st.columns([7, 3])
            with btn_c1: submit_msg = st.form_submit_button("Send Data 🚀")
            with btn_c2:
                if st.form_submit_button("🗑️ Clear"):
                    st.session_state.chat_messages = []
                    st.rerun()

        if submit_msg and user_text:
            if not nvidia_api_key:
                st.error("❌ Key Missing in Sidebar!")
            else:
                st.session_state.chat_messages.append({"role": "user", "content": user_text})
                with chat_box:
                    with st.chat_message("user"): st.markdown(user_text)
                with st.spinner("AI 1 Acknowledging..."):
                    try:
                        sys_prompt = "You are a receptionist. Acknowledge receipt and say: '✅ Data is ready! Please click the Sync Button to update tabs.' DO NOT generate timetable."
                        reply = call_nvidia([{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_text}], max_tokens=2500)
                        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                        with chat_box:
                            with st.chat_message("assistant"): st.markdown(reply)
                    except Exception as e:
                        st.error(f"AI 1 Error: {e}")

    with col_engine:
        st.subheader("🔄 AI-2 & Engine Runner")
        if st.button("🔄 AI 2: Extract & Sync Tabs", use_container_width=True):
            if not nvidia_api_key:
                st.error("❌ Key Missing in Sidebar!")
            else:
                all_msgs = [m["content"] for m in st.session_state.chat_messages if m["role"] == "user"]
                full_input = "\n\n".join(all_msgs)
                if len(full_input.strip()) < 10:
                    st.warning("⚠️ Pehle chat box mein apna school data paste karke 'Send Data' dabayein!")
                else:
                    with st.spinner("AI 2 JSON bana raha hai (1 se 2 minute lag sakte hain)..."):
                        try:
                            sys_p = (
                                "You are a strict JSON data extractor. Extract timetable parameters from the text and output ONLY RAW JSON.\n"
                                "{\n"
                                '  "working_days": 6,\n'
                                '  "periods_per_day": 7,\n'
                                '  "break_at": 4,\n'
                                '  "saturday_half_day": false,\n'
                                '  "classes": ["1-A", "1-B"],\n'
                                '  "teachers": [{"Teacher Name": "Amit Sharma", "Subject": "English", "Allowed Classes": "all", "Periods/Week (Per Class)": 6}],\n'
                                '  "fixed_rules": ["Rule 1"]\n'
                                "}"
                            )
                            raw_out = call_nvidia([{"role": "system", "content": sys_p}, {"role": "user", "content": full_input}], temp=0.0, max_tokens=4096)
                            data = extract_json_safe(raw_out)
                            if data:
                                if "working_days" in data: st.session_state.working_days = int(data["working_days"])
                                if "periods_per_day" in data: st.session_state.periods_per_day = int(data["periods_per_day"])
                                if "break_at" in data: st.session_state.break_at = int(data["break_at"])
                                if "saturday_half_day" in data: st.session_state.saturday_half_day = str(data["saturday_half_day"]).lower() == "true"
                                if "classes" in data and data["classes"]: st.session_state.classes_df = pd.DataFrame({"Class Name": data["classes"]})
                                if "teachers" in data and data["teachers"]: st.session_state.teachers_df = pd.DataFrame(data["teachers"])
                                if "fixed_rules" in data and data["fixed_rules"]: st.session_state.rules_df = pd.DataFrame({"Rule": data["fixed_rules"]})
                                st.success("🎉 BINGO! Tabs Successfully Update Ho Gaye!")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ AI 2 output parse nahi ho paya. Kripya dobara Sync dabayein.")
                        except Exception as e:
                            st.error(f"Sync Error: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔥 Run Google OR-Tools (Conflict-Free Solver)", type="primary", use_container_width=True):
            with st.spinner("Generating optimal conflict-free timetable..."):
                try:
                    c_list, p_labels, v_periods, ortools_tt, reqs = prepare_engine_data()
                    
                    w_days = int(st.session_state.working_days)
                    p_per_day = int(st.session_state.periods_per_day)
                    is_half = st.session_state.saturday_half_day
                    days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][:w_days]
                    num_days = len(days_list)

                    day_periods_map = {}
                    p_counter = 1
                    for d in days_list:
                        day_p_count = 4 if (d.lower() == "saturday" and is_half) else p_per_day
                        day_periods_map[d] = list(range(p_counter, p_counter + day_p_count))
                        p_counter += day_p_count

                    model = cp_model.CpModel()
                    
                    # Boolean decision variable: x[class][period][req_idx]
                    x = {c: {p: {r_idx: model.NewBoolVar(f"a_{c}_{p}_{r_idx}") 
                                 for r_idx in range(len(reqs[c]))} 
                             for p in v_periods} 
                         for c in c_list}

                    # 1. Exactly one assignment per period slot
                    for c in c_list:
                        for p in v_periods: 
                            model.AddExactlyOne([x[c][p][r_idx] for r_idx in range(len(reqs[c]))])
                        for r_idx in range(len(reqs[c])): 
                            model.AddExactlyOne([x[c][p][r_idx] for p in v_periods])

                    # 2. Strict Teacher Conflict Prevention (Zero double-booking)
                    all_teachers = {req[0] for c in c_list for req in reqs[c] if req[0] != "-"}
                    for p in v_periods:
                        for teacher in all_teachers:
                            t_assigns = [x[c][p][r_idx] for c in c_list for r_idx, req in enumerate(reqs[c]) if req[0] == teacher]
                            if len(t_assigns) > 1: 
                                model.AddAtMostOne(t_assigns)

                    # 3. Subject Distribution & Core Subject Daily Requirement
                    for c in c_list:
                        sub_to_indices = {}
                        for r_idx, req in enumerate(reqs[c]):
                            sub = req
                            if sub != "Free Period":
                                sub_to_indices.setdefault(sub, []).append(r_idx)

                        for sub, r_indices in sub_to_indices.items():
                            total_sub_periods = len(r_indices)
                            max_sub_per_day = max(1, (total_sub_periods + num_days - 1) // num_days)
                            
                            for d, d_periods in day_periods_map.items():
                                day_sub_sum = sum(x[c][p][r_idx] for p in d_periods for r_idx in r_indices)
                                # Overload prevention: maximum per day
                                model.Add(day_sub_sum <= max_sub_per_day)
                                
                                # CORE SUBJECT RULE: Agar basic subject (Maths, Science, SST, Hindi, English)
                                # ke periods weekly days ke barabar ya zyada hain, toh roz kam se kam 1 period zaroor lage!
                                if is_core_subject(sub) and total_sub_periods >= num_days:
                                    model.Add(day_sub_sum >= 1)

                    # 4. Consecutive Same Subject Avoidance (No back-to-back same subjects)
                    for c in c_list:
                        sub_to_indices = {}
                        for r_idx, req in enumerate(reqs[c]):
                            sub = req
                            if sub != "Free Period":
                                sub_to_indices.setdefault(sub, []).append(r_idx)

                        for d, d_periods in day_periods_map.items():
                            for i in range(len(d_periods) - 1):
                                p_curr = d_periods[i]
                                p_next = d_periods[i + 1]
                                for sub, r_indices in sub_to_indices.items():
                                    model.Add(sum(x[c][p_curr][r] for r in r_indices) + sum(x[c][p_next][r] for r in r_indices) <= 1)

                    # 5. First Period (P1) Free Period Avoidance
                    for c in c_list:
                        non_free_count = sum(1 for req in reqs[c] if req[0] != "-")
                        free_r_indices = [r_idx for r_idx, req in enumerate(reqs[c]) if req[0] == "-"]
                        if non_free_count >= num_days and free_r_indices:
                            for d, d_periods in day_periods_map.items():
                                p1 = d_periods[0]
                                model.Add(sum(x[c][p1][r_idx] for r_idx in free_r_indices) == 0)

                    # 6. Dynamic Teacher Daily Workload Cap (Fatigue prevention)
                    for teacher in all_teachers:
                        total_t_periods = sum(1 for c in c_list for req in reqs[c] if req[0] == teacher)
                        t_daily_cap = max(5, (total_t_periods + num_days - 1) // num_days + 1)
                        for d, d_periods in day_periods_map.items():
                            t_daily_assigns = [
                                x[c][p][r_idx] 
                                for c in c_list 
                                for p in d_periods 
                                for r_idx, req in enumerate(reqs[c]) 
                                if req[0] == teacher
                            ]
                            if len(t_daily_assigns) > t_daily_cap:
                                model.Add(sum(t_daily_assigns) <= t_daily_cap)

                    # 7. Pedagogical Optimization:
                    # - Core subjects (Maths, Science, English, Hindi, SST) in earlier morning periods (P1 to P5)
                    # - Co-curricular activities (Sports, Library, Art, Computer) in later periods
                    # - Free periods pushed to the very end of the day
                    obj_terms = []
                    for c in c_list:
                        for r_idx, req in enumerate(reqs[c]):
                            sub = req
                            is_core = is_core_subject(sub)
                            is_free = (req[0] == "-")
                            for d, d_periods in day_periods_map.items():
                                for slot_idx, p in enumerate(d_periods):
                                    if is_core:
                                        # Morning bias for core subjects
                                        obj_terms.append(slot_idx * x[c][p][r_idx])
                                    elif is_free:
                                        # Heavy penalty for early free periods
                                        obj_terms.append((len(d_periods) - slot_idx) * 6 * x[c][p][r_idx])
                                    else:
                                        # Activity subjects prefer afternoon/later periods
                                        obj_terms.append((len(d_periods) - slot_idx) * 2 * x[c][p][r_idx])
                    if obj_terms:
                        model.Minimize(sum(obj_terms))

                    # Solve Model
                    solver = cp_model.CpSolver()
                    solver.parameters.max_time_in_seconds = 20.0
                    status = solver.Solve(model)

                    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                        for c in c_list:
                            for p in v_periods:
                                for r_idx, req in enumerate(reqs[c]):
                                    if solver.Value(x[c][p][r_idx]) == 1:
                                        p_label_idx = -1
                                        for idx, label in enumerate(p_labels):
                                            if "LUNCH" not in label:
                                                p_label_idx += 1
                                                if p_label_idx == p - 1:
                                                    ortools_tt[c][idx] = "Free Period" if req[0] == "-" else f"{req} ({req[0]})"
                                                    break
                        df_res = pd.DataFrame(ortools_tt)
                        df_res.insert(0, "Day / Period", p_labels)
                        st.success(f"🔥 OR-Tools Success! (Status: {solver.StatusName(status)})")
                        st.dataframe(df_res, use_container_width=True, hide_index=True)
                    else:
                        st.error("❌ Deadlock detected. Constraints satisfy nahi ho paye. Neeche AI-3 se check karwayein.")
                except Exception as e:
                    st.error(f"Engine Error: {e}")

    st.markdown("---")
    st.subheader("🤖 Step 3: AI-3 Deadlock Diagnostics & Rule Fixer")
    ai3_input = st.text_area("AI-3 se baat karein ya 'Auto-Analyze' dabayein:", height=80)
    col_a1, col_a2 = st.columns([7, 3])
    with col_a1: submit_ai3 = st.button("Ask AI-3 & Update Rules 🛠️", use_container_width=True)
    with col_a2: auto_btn = st.button("🚨 Auto-Analyze", use_container_width=True)

    target_prompt = None
    if auto_btn:
        target_prompt = "Google OR-Tools fail ho raha hai. Mere live data aur rules ko check karke galti batao."
    elif submit_ai3 and ai3_input:
        target_prompt = ai3_input

    if target_prompt:
        if not nvidia_api_key:
            st.error("❌ Key Missing in Sidebar!")
        else:
            with st.spinner("AI-3 Analyzing..."):
                try:
                    c_list, p_labels, v_periods, _, _ = prepare_engine_data()
                    live_info = json.dumps({
                        "classes": c_list,
                        "teachers": st.session_state.teachers_df.to_dict("records"),
                        "rules": st.session_state.rules_df["Rule"].tolist()
                    })
                    sys_p = f"You are AI-3 Timetable Diagnostics. DATA:\n{live_info}\nHelp user troubleshoot. If updating rules, output JSON at the end: ```json\n{{\"updated_rules\": [\"Rule 1\"]}}\n```"
                    reply = call_nvidia([{"role": "system", "content": sys_p}, {"role": "user", "content": target_prompt}], temp=0.2, max_tokens=2500)
                    st.markdown(re.sub(r'```json\s*\{.*?\}\s*```', '', reply, flags=re.DOTALL))
                    m = re.search(r'```json\s*(\{.*?\})\s*```', reply, re.DOTALL)
                    if m:
                        r_data = json.loads(m.group(1))
                        if "updated_rules" in r_data:
                            st.session_state.rules_df = pd.DataFrame({"Rule": r_data["updated_rules"]})
                            st.success("✅ AI-3 ne Rules Tab update kar diya hai!")
                            time.sleep(2)
                            st.rerun()
                except Exception as e:
                    st.error(f"AI 3 Error: {e}")
