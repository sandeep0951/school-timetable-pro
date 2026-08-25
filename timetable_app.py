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

# Attempt to import Google OR-Tools
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

st.set_page_config(page_title="Advanced Timetable Pro (Dual AI)", layout="wide")

# ================= SECRETS BYPASS (SIDEBAR) =================
with st.sidebar:
    st.header("🔑 API Keys Setup")
    st.markdown("Dual AI Architecture:\n1. Chat Expert (70B)\n2. JSON Builder (8B)")
    nvidia_api_key = st.text_input("Nvidia Master Key (nvapi-...)", type="password")
    st.info("🛡️ Bina double quotes ke key dalein.")

# ================= DUAL AI FUNCTIONS =================
# AI 1: Chat Expert (Language Samajhne wala)
def chat_ai(messages):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {nvidia_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "meta/llama-3.1-70b-instruct", 
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 500
    }
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    if response.status_code != 200: raise Exception(f"Chat AI Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# AI 2: JSON Expert (Sirf Data nikalne wala)
def json_ai(prompt_text):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {nvidia_api_key}", "Content-Type": "application/json"}
    
    system_prompt = (
        "You are a strict data extractor. Extract 8 parameters from the user text and output ONLY RAW JSON. "
        "No explanations, no markdown tags. Output exactly like this format:\n"
        "{\n"
        '  "working_days": 6,\n'
        '  "periods_per_day": 8,\n'
        '  "break_at": 4,\n'
        '  "saturday_half_day": false,\n'
        '  "classes": ["1st A", "1st B"],\n'
        '  "teachers": [{"Teacher Name": "Mr. Rohan", "Subject": "Maths", "Allowed Classes": "All", "Periods/Week (Per Class)": 6}],\n'
        '  "fixed_rules": ["Rule 1", "Rule 2"]\n'
        "}"
    )
    
    payload = {
        "model": "meta/llama-3.1-8b-instruct", # Bijli ki tarah tez JSON ke liye
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.1,
        "max_tokens": 1500
    }
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    if response.status_code != 200: raise Exception(f"JSON AI Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]


st.title("🏫 Advanced Timetable Pro (Dual AI Engine)")

# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 8
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "saturday_half_day" not in st.session_state: st.session_state.saturday_half_day = False 
if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 40} for i in range(1, 9)]
    slots.insert(4, {"Slot": "LUNCH BREAK", "Duration (Mins)": 40})
    st.session_state.periods_timing_df = pd.DataFrame(slots)

if "classes_df" not in st.session_state: 
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["1st A", "1st B"]})

if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame({
        "Teacher Name": ["Mr. Rohan Das", "Coach Ravi"],
        "Subject": ["Maths", "Sports"],
        "Allowed Classes": ["All", "All"],
        "Periods/Week (Per Class)": [6, 4] 
    })

if "rules_df" not in st.session_state:
    st.session_state.rules_df = pd.DataFrame({"Rule": []})


# ================= UI TABS =================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🕒 1. Timings & Schedule", 
    "🏫 2. Classes & Sections", 
    "👨‍🏫 3. Teachers & Logic", 
    "⚙️ 4. Rules", 
    "🚀💬 5. Chat & Engine"
])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.working_days = st.number_input("1. Working Days", min_value=1, max_value=7, value=int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("2. Periods per Day", min_value=1, max_value=20, value=int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch Break AFTER period?", min_value=1, max_value=15, value=int(st.session_state.break_at))
        st.session_state.saturday_half_day = st.checkbox("4. Saturday Half-Day?", value=st.session_state.saturday_half_day)
    with col2:
        st.markdown("**School Timing:**")
        st.session_state.periods_timing_df = st.data_editor(st.session_state.periods_timing_df, use_container_width=True, hide_index=True)

with tab2:
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.session_state.rules_df = st.data_editor(st.session_state.rules_df, num_rows="dynamic", use_container_width=True)

with tab5:
    col_chat, col_engine = st.columns([4, 6], gap="large")
    
    with col_chat:
        col_c1, col_c2 = st.columns([7, 3])
        with col_c1: st.subheader("💬 AI 1: Prompt Expert")
        with col_c2:
            if st.button("🗑️ Clear"): del st.session_state["chat_messages"]; st.rerun()

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "system", "content": "Aap ek Timetable assistant ho. User ka data padho aur Hindi/Hinglish me batao ki sab sahi he ya kuch bacha hai."},
                {"role": "assistant", "content": "Namaste! Main AI-1 hoon. Kripya apna poora data bhejein, main padh kar confirm karunga."}
            ]

        chat_container = st.container(height=450)
        with chat_container:
            for message in st.session_state.chat_messages:
                if message["role"] != "system":
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        with st.form("chat_input_form", clear_on_submit=True):
            prompt = st.text_area("Apna data yahan paste karein:", height=120)
            submit_chat = st.form_submit_button("Send to AI 1 🚀")

        if submit_chat and prompt:
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"): st.markdown(prompt)

            if not nvidia_api_key: st.error("❌ Key Missing!")
            else:
                with st.spinner("AI 1 is reading your prompt..."):
                    try:
                        reply = chat_ai(st.session_state.chat_messages)
                        with chat_container:
                            with st.chat_message("assistant"): st.markdown(reply)
                        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.error(f"AI 1 Error: {e}")

    with col_engine:
        st.subheader("⚙️ Action Center")
        
        # ================= AI 2: JSON SYNC =================
        if st.button("🔄 AI 2: Convert to JSON & Sync", use_container_width=True):
            if not nvidia_api_key: st.error("Key Missing!")
            else:
                with st.spinner("AI 2 (JSON Builder) is working..."):
                    user_msgs = [msg['content'] for msg in st.session_state.chat_messages if msg["role"] == "user"]
                    full_text = " ".join(user_msgs)
                    
                    if len(full_text) < 10:
                        st.warning("Pehle chat box me kuch data bhejein!")
                    else:
                        try:
                            raw_output = json_ai(full_text)
                            
                            # Clean up the output (remove markdown)
                            clean_output = raw_output.strip()
                            if clean_output.startswith("```json"): clean_output = clean_output[7:]
                            elif clean_output.startswith("```"): clean_output = clean_output[3:]
                            if clean_output.endswith("```"): clean_output = clean_output[:-3]
                            
                            clean_output = clean_output.strip()
                            part_data = json.loads(clean_output)
                            
                            # Update parameters
                            if "working_days" in part_data: st.session_state.working_days = int(part_data["working_days"])
                            if "periods_per_day" in part_data: st.session_state.periods_per_day = int(part_data["periods_per_day"])
                            if "break_at" in part_data: st.session_state.break_at = int(part_data["break_at"])
                            if "saturday_half_day" in part_data: 
                                st.session_state.saturday_half_day = str(part_data["saturday_half_day"]).lower() == "true"
                            
                            if "classes" in part_data and part_data["classes"]:
                                st.session_state.classes_df = pd.DataFrame({"Class Name": part_data["classes"]})
                                
                            if "teachers" in part_data and part_data["teachers"]:
                                st.session_state.teachers_df = pd.DataFrame(part_data["teachers"])
                                
                            if "fixed_rules" in part_data and part_data["fixed_rules"]:
                                st.session_state.rules_df = pd.DataFrame({"Rule": part_data["fixed_rules"]})
                                
                            st.success("✅ AI 2 ne JSON bana diya aur Tabs update kar diye!")
                            st.rerun()
                        except json.JSONDecodeError:
                            st.error("❌ AI 2 failed to build valid JSON. Raw output below:")
                            st.code(clean_output)
                        except Exception as e:
                            st.error(f"❌ AI 2 Error: {e}")

        st.markdown("---")
        # RUN ENGINE BUTTON
        if st.button("🚀 Run Timetable Engine", type="primary", use_container_width=True):
            with st.spinner("Applying Rules & Running Engine..."):
                sys.setrecursionlimit(5000)
                
                classes_list = st.session_state.classes_df["Class Name"].dropna().tolist()
                teachers_list = st.session_state.teachers_df.to_dict('records')
                periods_per_day = st.session_state.periods_per_day
                working_days = st.session_state.working_days
                break_at = st.session_state.break_at
                fixed_rules = st.session_state.rules_df["Rule"].dropna().tolist()
                is_sat_half = st.session_state.saturday_half_day
                
                rule_max_consecutive = 10 
                for r in fixed_rules:
                    r_lower = r.lower()
                    if "consecutive" in r_lower or "continuous" in r_lower:
                        nums = re.findall(r'\d+', r_lower)
                        if nums: rule_max_consecutive = int(nums[0])
                
                days_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                period_labels = []
                valid_periods = []
                global_p_idx = 0
                
                for d in range(working_days):
                    day_name = days_str[d]
                    if day_name.lower() == "saturday" and is_sat_half: current_day_periods = 4
                    else: current_day_periods = periods_per_day
                    
                    for i in range(1, current_day_periods + 1):
                        global_p_idx += 1
                        period_labels.append(f"{day_name} - P{i}")
                        valid_periods.append(global_p_idx)
                        if i == break_at and not (day_name.lower() == "saturday" and is_sat_half): 
                            period_labels.append(f"{day_name} - LUNCH")
                
                total_weekly_periods = len(valid_periods)
                initial_timetable = {c: ["Free"] * len(period_labels) for c in classes_list} 
                for c in classes_list:
                    for (idx, label) in enumerate(period_labels):
                        if "LUNCH" in label: initial_timetable[c][idx] = "LUNCH / BREAK"
                            
                initial_busy_teachers = {i: set() for i in range(len(period_labels))}
                class_requirements = {c: [] for c in classes_list}
                
                for t in teachers_list:
                    t_name = t.get("Teacher Name", "")
                    t_sub_raw = str(t.get("Subject", ""))
                    t_allowed_str = str(t.get("Allowed Classes", "")).strip()
                    try: p_per_class = int(t.get("Periods/Week (Per Class)", working_days))
                    except: p_per_class = working_days
                        
                    if p_per_class > total_weekly_periods: p_per_class = total_weekly_periods

                    if str(t_allowed_str).lower() == "all" or str(t_allowed_str) == "":
                        actual_classes = classes_list
                    else:
                        allowed_lower = [x.strip().lower() for x in str(t_allowed_str).split(",")]
                        actual_classes = [c for c in classes_list if c.lower() in allowed_lower]
                        
                    for c in actual_classes:
                        for sub in [s.strip() for s in t_sub_raw.split(",")]:
                            for _ in range(p_per_class):
                                class_requirements[c].append((t_name, sub))

                for c in classes_list:
                    if len(class_requirements[c]) > total_weekly_periods:
                        random.shuffle(class_requirements[c]) 
                        class_requirements[c] = class_requirements[c][:total_weekly_periods]
                    while len(class_requirements[c]) < total_weekly_periods:
                        class_requirements[c].append(("Free Period", ""))

                st.info(f"🔄 Running Custom Engine...")
                
                custom_timetable = copy.deepcopy(initial_timetable)
                custom_busy = copy.deepcopy(initial_busy_teachers)
                custom_reqs = copy.deepcopy(class_requirements)
                custom_start_time = time_module.time()
                
                def solve_custom(p_idx, c_idx):
                    if time_module.time() - custom_start_time > 15.0: return False
                    if p_idx >= len(period_labels): return True
                    if "LUNCH" in period_labels[p_idx]: return solve_custom(p_idx + 1, 0)
                    
                    c = classes_list[c_idx]
                    next_c_idx = c_idx + 1
                    next_p_idx = p_idx
                    if next_c_idx >= len(classes_list):
                        next_c_idx = 0
                        next_p_idx += 1
                    
                    if custom_timetable[c][p_idx] != "Free": return solve_custom(next_p_idx, next_c_idx)
                    if len(custom_reqs[c]) == 0: return solve_custom(next_p_idx, next_c_idx)
                    
                    valid_reqs = []
                    seen_reqs = set()
                    for req in custom_reqs[c]:
                        if req not in seen_reqs: 
                            seen_reqs.add(req)
                            if req[0] not in custom_busy[p_idx] or req[0] == "Free Period":
                                t_name_check = req[0]
                                if t_name_check != "Free Period":
                                    consecutive = 0
                                    for back_p in range(p_idx - 1, -1, -1):
                                        if "LUNCH" in period_labels[back_p]: break
                                        if t_name_check in custom_busy[back_p]: consecutive += 1
                                        else: break
                                    if consecutive >= rule_max_consecutive: continue 
                                valid_reqs.append(req)
                    
                    random.shuffle(valid_reqs) 
                    
                    for req in valid_reqs:
                        t_name, sub = req
                        if t_name == "Free Period": custom_timetable[c][p_idx] = "Free Period"
                        else:
                            custom_timetable[c][p_idx] = f"{sub} ({t_name})"
                            custom_busy[p_idx].add(t_name)
                        
                        custom_reqs[c].remove(req) 
                        if solve_custom(next_p_idx, next_c_idx): return True
                        
                        custom_timetable[c][p_idx] = "Free"
                        if t_name != "Free Period": custom_busy[p_idx].remove(t_name)
                        custom_reqs[c].append(req) 
                    return False

                if solve_custom(0, 0):
                    df = pd.DataFrame(custom_timetable)
                    df.insert(0, "Day / Period", period_labels)
                    st.success("✅ Timetable Generated Successfully!")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.error("Engine failed due to strict rules. Try modifying rules.")
