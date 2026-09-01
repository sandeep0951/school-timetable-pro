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
    ORTOLS_AVAILABLE = True
except ImportError:
    ORTOLS_AVAILABLE = False

st.set_page_config(
    page_title="Advanced Timetable Pro (Triple AI System)",
    layout="wide"
)

# ================= SECRETS BYPASS (SIDEBAR) =================
with st.sidebar:
    st.header("🔑 API Keys Setup")
    st.markdown(
        "Triple AI Architecture:\n"
        "1. Data Setup: DeepSeek V4\n"
        "2. JSON Sync: DeepSeek V4\n"
        "3. Rule Fixer: DeepSeek V4"
    )
    nvidia_api_key = st.text_input(
        label="Nvidia Master Key (nvapi-...)",
        type="password"
    )
    if ORTOLS_AVAILABLE:
        st.success("✅ Google OR-Tools is Active!")
    else:
        st.error("❌ Google OR-Tools is Missing!")
    st.info("🛡️ Bina double quotes ke key dalein.")

# ================= TRIPLE AI FUNCTIONS =================

# AI 1: Chat Collector (DeepSeek V4 Pro)
def chat_ai(messages):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    system_instruction = {
        "role": "system",
        "content": (
            "You are a receptionist. Acknowledge data and say: "
            "'✅ Data is ready. Please click the Sync Button to update tabs.' "
            "DO NOT generate timetable."
        )
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

# AI 2: JSON Expert (DeepSeek V4 Pro)
def json_ai(prompt_text):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are a strict JSON data extractor. Extract timetable parameters from the text and output ONLY RAW JSON. "
        "CRITICAL RULES: \n"
        "1. DO NOT invent data. Use ONLY the data provided.\n"
        "2. Ensure all arrays are properly closed.\n"
        "3. EXTRACT ALL RULES and put them in the 'fixed_rules' array.\n"
        "4. Format exactly like this:\n"
        "{\n"
        '  "working_days": 6,\n'
        '  "periods_per_day": 7,\n'
        '  "break_at": 4,\n'
        '  "saturday_half_day": false,\n'
        '  "classes": ["1-A", "1-B"],\n'
        '  "teachers": [{"Teacher Name": "Amit Sharma", "Subject": "English", "Allowed Classes": "1-A, 1-B", "Periods/Week (Per Class)": 4}],\n'
        '  "fixed_rules": ["Rule 1: No double booking"]\n'
        "}"
    )
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.0,
        "max_tokens": 4096
    }
    response = requests.post(url, headers=headers, json=payload, timeout=300)
    if response.status_code != 200:
        raise Exception(f"JSON AI Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# AI 3: Interactive Diagnostics & Rule Fixer (DeepSeek V4 Pro)
def chat_ai3(user_input, current_data_str, history):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are 'AI-3', an expert Timetable Diagnostics and Rule Fixer AI.\n"
        "You help the user troubleshoot why their Timetable Engine (OR-Tools) is failing (Deadlock). "
        "You communicate in friendly Hinglish (Hindi + English).\n\n"
        f"CURRENT LIVE APP DATA (From Tabs):\n{current_data_str}\n\n"
        "YOUR DUTIES:\n"
        "1. DIAGNOSE: Analyze the data above. Look for bottlenecks (e.g., classes requiring more periods than working days, "
        "teachers overloaded, conflicting strict rules like 'max 2 consecutive periods' combined with high frequency subjects). "
        "Explain clearly WHY OR-Tools failed.\n"
        "2. SUGGEST: Provide 2-3 bullet points on what needs to be changed in the data or rules.\n"
        "3. RULE MODIFICATION: If the user explicitly asks you to change, add, or delete a rule (or if they accept your suggestion "
        "to remove a strict rule), you MUST perform the action and output the entirely new, updated list of rules inside a specific "
        "JSON block format at the end of your message.\n\n"
        "JSON FORMAT FOR UPDATING RULES:\n"
        "```json\n"
        "{\n"
        '  "updated_rules": ["Rule 1", "Rule 2", "New Rule"]\n'
        "}\n"
        "```\n"
        "(Only output the JSON block if a rule needs to be updated. Otherwise, just reply with text analysis)."
    )
    messages = [{"role": "system", "content": system_prompt}] + history
    messages.append({"role": "user", "content": user_input})
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1500
    }
    response = requests.post(url, headers=headers, json=payload, timeout=180)
    if response.status_code != 200:
        raise Exception(f"AI 3 Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]


# --- HELPER FUNCTION: RANGE PARSER ---
def parse_allowed_classes(allowed_str, all_classes):
    s = str(allowed_str).strip()
    if not s or s.lower() == "all":
        return list(all_classes)
    
    # Range format support like "Classes 1-A to 5-B" or "1-A to 10-B"
    range_match = re.search(r'(\d+)\s*[-_]?\s*([A-Za-z])\s*(?:to|-)\s*(\d+)\s*[-_]?\s*([A-Za-z])', s, re.IGNORECASE)
    if range_match:
        start_grade = int(range_match.group(1))
        end_grade = int(range_match.group(3))
        matched = []
        for c in all_classes:
            g_match = re.match(r'(\d+)', c)
            if g_match:
                g = int(g_match.group(1))
                if start_grade <= g <= end_grade:
                    matched.append(c)
        if matched:
            return matched
            
    # Comma-separated fallback
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
            
    days_str = [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]
    period_labels = []
    valid_periods = []
    global_p_idx = 0
    
    for d in range(working_days):
        day_name = days_str[d]
        if day_name.lower() == "saturday" and is_sat_half:
            current_day_periods = 4
        else:
            current_day_periods = periods_per_day

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
    class_requirements = {c: [] for c in classes_list}
    
    for t in teachers_list:
        t_name = t.get("Teacher Name", "")
        t_sub_raw = str(t.get("Subject", ""))
        t_allowed_str = str(t.get("Allowed Classes", "")).strip()
        try:
            p_per_class = int(t.get("Periods/Week (Per Class)", 4))
        except Exception:
            p_per_class = 4
        if p_per_class > total_weekly_periods:
            p_per_class = total_weekly_periods

        actual_classes = parse_allowed_classes(t_allowed_str, classes_list)

        for c in actual_classes:
            for sub in [s.strip() for s in t_sub_raw.split(",")]:
                for _ in range(p_per_class):
                    class_requirements[c].append((t_name, sub))

    for c in classes_list:
        if len(class_requirements[c]) > total_weekly_periods:
            random.shuffle(class_requirements[c])
            class_requirements[c] = class_requirements[c][:total_weekly_periods]
        while len(class_requirements[c]) < total_weekly_periods:
            class_requirements[c].append(("-", "-"))
        
    return (
        classes_list,
        period_labels,
        valid_periods,
        initial_timetable,
        initial_busy_teachers,
        class_requirements,
        rule_max_consecutive
    )


st.title("🏫 Advanced Timetable Pro (Triple AI System)")

# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state:
    st.session_state.working_days = 6

if "periods_per_day" not in st.session_state:
    st.session_state.periods_per_day = 7

if "break_at" not in st.session_state:
    st.session_state.break_at = 4

if "saturday_half_day" not in st.session_state:
    st.session_state.saturday_half_day = False

if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 45} for i in range(1, 8)]
    slots.insert(4, {"Slot": "LUNCH BREAK", "Duration (Mins)": 30})
    st.session_state.periods_timing_df = pd.DataFrame(slots)

if "classes_df" not in st.session_state:
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["1-A", "1-B"]})

if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame({
        "Teacher Name": ["Amit Sharma", "Rahul Jain"],
        "Subject": ["English", "Mathematics"],
        "Allowed Classes": ["1-A to 5-B", "1-A to 5-B"],
        "Periods/Week (Per Class)": [4, 5]
    })

if "rules_df" not in st.session_state:
    st.session_state.rules_df = pd.DataFrame({"Rule": []})

if "ai3_messages" not in st.session_state: 
    st.session_state.ai3_messages = [{
        "role": "assistant",
        "content": "Namaste Sir! Main AI-3 (The Fixer) hoon. Agar aapka timetable Google OR-Tools par fail ho raha hai, toh upar wala **'Auto-Analyze'** button dabayein!"
    }]

# ================= UI TABS =================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🕒 Timings",
    "🏫 Classes",
    "👨🏫 Teachers",
    "⚙️ Rules",
    "🚀💬 AI & Engine Center"
])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.working_days = st.number_input(
            label="1. Working Days",
            min_value=1,
            max_value=7,
            value=int(st.session_state.working_days)
        )
        st.session_state.periods_per_day = st.number_input(
            label="2. Periods per Day",
            min_value=1,
            max_value=20,
            value=int(st.session_state.periods_per_day)
        )
        st
