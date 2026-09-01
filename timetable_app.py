import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
import json
import random
import sys
import copy
import re
import requests

try:
    from ortools.sat.python import cp_model
    ORTOLS_AVAILABLE = True
except ImportError:
    ORTOLS_AVAILABLE = False

st.set_page_config(page_title="Advanced Timetable Pro (Triple AI System)", layout="wide")

# ================= SECRETS BYPASS (SIDEBAR) =================
with st.sidebar:
    st.header("🔑 API Keys Setup")
    st.markdown("Triple AI Architecture:\n1. Data Setup: DeepSeek V4\n2. JSON Sync: DeepSeek V4\n3. Rule Fixer: DeepSeek V4")
    nvidia_api_key = st.text_input("Nvidia Master Key (nvapi-...)", type="password")
    if ORTOLS_AVAILABLE:
        st.success("✅ Google OR-Tools is Active!")
    else:
        st.error("❌ Google OR-Tools is Missing!")
    st.info("🛡️ Bina double quotes ke key dalein.")

# ================= TRIPLE AI FUNCTIONS =================

# AI 1: Fast Chat Collector
def chat_ai(messages):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    system_instruction = {
        "role": "system",
        "content": "You are a receptionist. Acknowledge data and say: '✅ Data is ready. Please click the Sync Button to update tabs.' DO NOT generate timetable."
    }
    safe_messages = [system_instruction] + [m for m in messages if m.get("role") != "system"]
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": safe_messages,
        "temperature": 0.1,
        "max_tokens": 2500
    }
    response = requests.post(url, headers=headers, json=payload, timeout=300)
    if response.status_code != 200:
        raise Exception(f"Chat AI Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# AI 2: JSON Expert
def json_ai(prompt_text):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    system_prompt = (
        "Extract timetable parameters from text and output ONLY valid RAW JSON:\n"
        '{"working_days": 6, "periods_per_day": 7, "break_at": 4, "saturday_half_day": false, '
        '"classes": ["1-A", "1-B"], '
        '"teachers": [{"Teacher Name": "Amit Sharma", "Subject": "English", "Allowed Classes": "1-A, 1-B", "Periods/Week (Per Class)": 4}], '
        '"fixed_rules": ["Rule 1"]}'
    )
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt_text}],
        "temperature": 0.0,
        "max_tokens": 4096
    }
    response = requests.post(url, headers=headers, json=payload, timeout=300)
    if response.status_code != 200:
        raise Exception(f"JSON AI Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# AI 3: Interactive Diagnostics & Rule Fixer
def chat_ai3(user_input, current_data_str, history):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are AI-3, an expert Timetable Diagnostics and Rule Fixer AI in Hinglish.\n"
        f"CURRENT DATA: {current_data_str}\n"
        "1. Diagnose why timetable failed.\n"
        "2. Suggest changes.\n"
        "3. Output updated rules in JSON block: ```json\n{\"updated_rules\": [\"Rule 1\"]}\n```"
    )
    messages = [{"role": "system", "content": system_prompt}] + history
    messages.append({"role": "user", "content": user_input})
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4096
    }
    response = requests.post(url, headers=headers, json=payload, timeout=600)
    if response.status_code != 200:
        raise Exception(f"AI 3 Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# --- HELPER FUNCTION: RANGE PARSER ---
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

# --- HELPER FUNCTION FOR DATA PREP ---
def prepare_engine_data():
    sys.setrecursionlimit(5000)
    classes_list = st.session_state.classes_df["Class Name"].dropna().tolist()
    teachers_list = st.session_state.teachers_df.to_dict("records")
    periods_per_day = st.session_state.periods_per_day
    working_days = st.session_state.working_days
    break_at = st.session_state.break_at
    fixed_rules = st.session_state.rules_df["Rule"].dropna().tolist()
    is_sat_half = st.session_state.saturday_half_day
    
    rule_max_consecutive = 10 
    for r in fixed_rules:
        r_lower = r.lower()
        if "consecutive" in r_lower or "continuous" in r_lower:
            nums = re.findall(r"\d+", r_lower)
            if nums:
                rule_max_consecutive = int(nums[0])
            
    days_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    period_labels = []
    valid_periods = []
    global_p_idx = 0
    
    for d in range(working_days):
        day_name = days_str[d]
        current_day_periods = 4 if (day_name.lower() == "saturday" and is_sat_half) else periods_per_day
        for i in range(1, current_day_periods + 1):
            global_p_idx += 1
            period_labels.append(f"{day_name} - P{i}")
            valid_periods.append(global_p_idx)
            if i == break_at and not (day_name.lower() == "saturday" and is_sat_half): 
                period_labels.append(f"{day_name} - LUNCH")
                
    total_weekly_periods = len(valid_periods)
    initial_timetable = {c: ["EMPTY"] * len(period_labels) for c in classes_list} 
    for c in classes_list:
        for idx, label in enumerate(period_labels):
            if "LUNCH" in label:
                initial_timetable[c][idx] = "LUNCH / BREAK"
                
    initial_busy_teachers = {i: set() for i in range(len(period_labels))}
    
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
            eligible.sort(key=lambda t: t["load"])
            chosen = eligible[0]
            chosen["load"] += p_count
            for _ in range(p_count):
                class_requirements[c].append((chosen["name"], sub))

    for c in classes_list:
        if len(class_requirements[c]) > total_weekly_periods:
            random.shuffle(class_requirements[c])
            class_requirements[c] = class_requirements[c][:total_weekly_periods]
        while len(class_requirements[c]) < total_weekly_periods:
            class_requirements[c].append(("-", "Free Period"))
        
    return classes_list, period_labels, valid_periods, initial_timetable, initial_busy_teachers, class_requirements, rule_max_consecutive

st.title("🏫 Advanced Timetable Pro (Triple AI System)")

# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 7
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "saturday_half_day" not in st.session_state: st.session_state.saturday_half_day = False
if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 45} for i in range(1, 8)]
    slots.insert(4, {"Slot": "LUNCH BREAK", "Duration (Mins)": 30})
    st.session_state.periods_timing_df = pd.DataFrame(slots)
if "classes_df" not in st.session_state: st.session_state.classes_df = pd.DataFrame({"Class Name": ["1-A", "1-B"]})
if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame({
        "Teacher Name": ["Amit Sharma", "Rahul Jain"],
        "Subject": ["English", "Mathematics"],
        "Allowed Classes": ["1-A to 5-B", "1-A to 5-B"],
        "Periods/Week (Per Class)": [4, 5]
    })
if "rules_df" not in st.session_state: st.session_state.rules_df = pd.DataFrame({"Rule": []})
if "ai3_messages" not in st.session_state: 
    st.session_state.ai3_messages = [{"role": "assistant", "content": "Namaste Sir! Main AI-3 (The Fixer) hoon. Agar timetable fail ho, toh Auto-Analyze dabayein!"}]

# ================= UI TABS =================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🕒 Timings", "🏫 Classes", "👨🏫 Teachers", "⚙️ Rules", "🚀💬 AI & Engine Center"])

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
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        chat_container = st.container(height=300)
        with chat_container:
            for message in st.session_state.chat_messages:
                if message.get("role") != "system":
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        with st.form("chat_input_form", clear_on_submit=True):
            prompt = st.text_area("Paste Data Here:", height=80)
            c1, c2 = st.columns([7, 3])
            with c1:
                submit_chat = st.form_submit_button("Send Data 🚀")
            with c2: 
                if st.form_submit_button("🗑️ Clear"):
                    st.session_state.chat_messages = []
                    st.rerun()

        if submit_chat and prompt:
            if not nvidia_api_key:
                st.error("❌ Key Missing!")
            else:
                st.session_state.chat_messages.append({"role": "user", "content": prompt})
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(prompt)
                with st.spinner("AI 1 is processing..."):
                    try:
                        reply = chat_ai(st.session_state.chat_messages[-3:])
                        with chat_container:
                            with st.chat_message("assistant"):
                                st.markdown(reply)
                        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.error(f"AI 1 Error: {e}")

    with col_engine:
        if st.button("🔄 AI 2: Extract & Sync Tabs", use_container_width=True):
            if not nvidia_api_key:
                st.error("Key Missing!")
            else:
                with st.spinner("AI 2 JSON bana raha hai (1 se 3 minute lag sakte hain)..."):
                    user_msgs = [msg["content"] for msg in st.session_state.chat_messages if msg.get("role") == "user"]
                    full_text = " ".join(user_msgs)
                    if len(full_text) < 10:
                        st.warning("Pehle chat box me apna data paste karein!")
                    else:
                        try:
                            raw_output = json_ai(full_text)
                            start_idx = raw_output.find("{")
                            end_idx = raw_output.rfind("}")
                            clean_output = raw_output[start_idx:end_idx+1] if start_idx != -1 and end_idx != -1 else raw_output
                            clean_output = re.sub(r",\s*}", "}", clean_output)
                            clean_output = re.sub(r",\s*]", "]", clean_output)
                                
                            part_data = json.loads(clean_output)
                            updated = False
                            if "working_days" in part_data:
                                st.session_state.working_days = int(part_data["working_days"])
                                updated = True
                            if "periods_per_day" in part_data:
                                st.session_state.periods_per_day = int(part_data["periods_per_day"])
                                updated = True
                            if "break_at" in part_data:
                                st.session_state.break_at = int(part_data["break_at"])
                                updated = True
                            if "saturday_half_day" in part_data:
                                st.session_state.saturday_half_day = str(part_data["saturday_half_day"]).lower() == "true"
                            if "classes" in part_data and part_data["classes"]:
                                st.session_state.classes_df = pd.DataFrame({"Class Name": part_data["classes"]})
                                updated = True
                            if "teachers" in part_data and part_data["teachers"]:
                                st.session_state.teachers_df = pd.DataFrame(part_data["teachers"])
                                updated = True
                            if "fixed_rules" in part_data and part_data["fixed_rules"]:
                                st.session_state.rules_df = pd.DataFrame({"Rule": part_data["fixed_rules"]})
                                updated = True
                                
                            if updated:
                                st.success("🎉 BINGO! Tabs update ho gaye!")
                                time_module.sleep(2)
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ AI 2 Error: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        col_e1, col_e2 = st.columns(2)
        
        with col_e1:
            if st.button("🚀 Run Python Engine", use_container_width=True):
                with st.spinner("Python Engine is working..."):
                    c_list, p_labels, v_periods, init_tt, init_busy, c_reqs, rule_max = prepare_engine_data()
                    custom_start = time_module.time()
                    
                    def solve_custom(p_idx, c_idx):
                        if time_module.time() - custom_start > 10.0:
                            return False
                        if p_idx >= len(p_labels):
                            return True
                        if "LUNCH" in p_labels[p_idx]:
                            return solve_custom(p_idx + 1, 0)
                        c = c_list[c_idx]
                        nxt_c, nxt_p = (0, p_idx + 1) if c_idx + 1 >= len(c_list) else (c_idx + 1, p_idx)
                        
                        if init_tt[c][p_idx] != "EMPTY" or len(c_reqs[c]) == 0:
                            return solve_custom(nxt_p, nxt_c)
                        
                        valid_reqs, seen = [], set()
                        for req in c_reqs[c]:
                            if req not in seen:
                                seen.add(req)
                                if req[0] not in init_busy[p_idx] or req[0] == "-":
                                    if req[0] != "-":
                                        consec = 0
                                        curr_day = p_labels[p_idx].split(" - ")[0]
                                        for back_p in range(p_idx - 1, -1, -1):
                                            if "LUNCH" in p_labels[back_p]:
                                                continue
                                            back_day = p_labels[back_p].split(" - ")[0]
                                            if back_day != curr_day:
                                                break
                                            if req[0] in init_busy[back_p]:
                                                consec += 1
                                            else:
                                                break
                                        if consec >= rule_max:
                                            continue 
                                    valid_reqs.append(req)
                        random.shuffle(valid_reqs) 
                        for req in valid_reqs:
                            t_name, sub = req
                            init_tt[c][p_idx] = "---" if t_name == "-" else f"{sub} ({t_name})"
                            if t_name != "-":
                                init_busy[p_idx].add(t_name)
                            c_reqs[c].remove(req) 
                            if solve_custom(nxt_p, nxt_c):
                                return True
                            init_tt[c][p_idx] = "EMPTY"
                            if t_name != "-":
                                init_busy[p_idx].remove(t_name)
                            c_reqs[c].append(req) 
                        return False

                    if solve_custom(0, 0):
                        df = pd.DataFrame(init_tt)
                        df.insert(0, "Day / Period", p_labels)
                        st.success("✅ Python Engine Success! Check below:")
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.warning("⚠️ Python Engine failed. Use Google OR-Tools for instant optimal solving.")

        with col_e2:
            if st.button("🔥 Run Google OR-Tools", type="primary", use_container_width=True):
                with st.spinner("Advanced OR-Tools Engine working..."):
                    if not ORTOLS_AVAILABLE:
                        st.error("❌ OR-Tools not installed!")
                    else:
                        c_list, p_labels, v_periods, ortools_tt, _, ortools_reqs, _ = prepare_engine_data()
                        model = cp_model.CpModel()
                        x = {
                            c: {
                                p: {
                                    r_idx: model.NewBoolVar(f"assign_{c}_{p}_{r_idx}")
                                    for r_idx in range(len(ortools_reqs[c]))
                                }
                                for p in v_periods
                            }
                            for c in c_list
                        }

                        for c in c_list:
                            for p in v_periods:
                                model.AddExactlyOne([x[c][p][r_idx] for r_idx in range(len(ortools_reqs[c]))])
                            for r_idx in range(len(ortools_reqs[c])):
                                model.AddExactlyOne([x[c][p][r_idx] for p in v_periods])

                        all_teachers = {req[0] for c in c_list for req in ortools_reqs[c] if req[0] != "-"}
                        for p in v_periods:
                            for teacher in all_teachers:
                                t_assigns = [
                                    x[c][p][r_idx]
                                    for c in c_list
                                    for r_idx, req in enumerate(ortools_reqs[c])
                                    if req[0] == teacher
                                ]
                                if len(t_assigns) > 1:
                                    model.AddAtMostOne(t_assigns)

                        solver = cp_model.CpSolver()
                        solver.parameters.max_time_in_seconds = 15.0 
                        status = solver.Solve(model)

                        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                            for c in c_list:
                                for p in v_periods:
                                    for r_idx, req in enumerate(ortools_reqs[c]):
                                        if solver.Value(x[c][p][r_idx]) == 1:
                                            p_label_idx = -1
                                            for idx, label in enumerate(p_labels):
                                                if not "LUNCH" in label:
                                                    p_label_idx += 1
                                                    if p_label_idx == p - 1:
                                                        ortools_tt[c][idx] = "Free Period" if req[0] == "-" else f"{req} ({req[0]})"
                                                        break
                            df = pd.DataFrame(ortools_tt)
                            df.insert(0, "Day / Period", p_labels)
                            st.success(f"🔥 OR-Tools Success! (Status: {solver.StatusName(status)})")
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.error("❌ OR-Tools Failed. Deadlock. Neeche 'Auto-Analyze' Button Dabayein!")

    st.markdown("---")
    
    # ================= AI 3: DEADLOCK & RULE FIXER CHAT =================
    st.markdown("### 🤖 Step 3: AI-3 Deadlock Fixer & Rule Manager")
    
    col_a3_1, col_a3_2 = st.columns([7, 3])
    with col_a3_1:
        auto_analyze_btn = st.button("🚨 Auto-Analyze OR-Tools Error (Deadlock)", type="secondary", use_container_width=True)
    with col_a3_2:
        if st.button("🗑️ Clear AI-3 Chat", use_container_width=True):
            st.session_state.ai3_messages = st.session_state.ai3_messages[:1]
            st.rerun()
            
    ai3_container = st.container(height=350)
    with ai3_container:
        for message in st.session_state.ai3_messages:
            if message.get("role") != "system":
                display_text = re.sub(r"```json\s*\{.*?\}\s*```", "", message.get("content", ""), flags=re.DOTALL).strip()
                if display_text:
                    with st.chat_message(message["role"]):
                        st.markdown(display_text)

    with st.form("ai3_form", clear_on_submit=True):
        ai3_prompt = st.text_area("AI-3 se baat karein (Ya upar wala 'Auto-Analyze' button dabayein):", height=80)
        submit_ai3 = st.form_submit_button("Ask AI-3 & Update Rules 🛠️")

    trigger_prompt = None
    if auto_analyze_btn:
        trigger_prompt = "Google OR-Tools timetable banane mein fail ho gaya hai (Deadlock). Kripya mere current data aur rules ko check karo, galti pakdo, aur batao mujhe kya change karna chahiye?"
    elif submit_ai3 and ai3_prompt:
        trigger_prompt = ai3_prompt

    if trigger_prompt:
        if not nvidia_api_key:
            st.error("❌ Key Missing!")
        else:
            st.session_state.ai3_messages.append({"role": "user", "content": trigger_prompt})
            with ai3_container:
                with st.chat_message("user"):
                    st.markdown(trigger_
