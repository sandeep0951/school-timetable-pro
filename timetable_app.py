import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
from groq import Groq
import json
import random
import sys
import copy

# Attempt to import Google OR-Tools
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

# App Configuration
st.set_page_config(page_title="Advanced Timetable Pro (Weekly 8-Point Edition)", layout="wide")

# Initialize Groq Client
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_api_key)
except:
    client = None

# App Header
st.title("🏫 Advanced Timetable Pro (Weekly Engine + 8-Point AI)")
st.markdown("Tier 1: Custom Python Logic | Tier 2: Google OR-Tools | AI Assistant")

if not ORTOOLS_AVAILABLE:
    st.warning("⚠️ Google 'ortools' is not installed. The app will only use the Custom Python Engine. Add 'ortools' to requirements.txt for the enterprise fallback.")

# --- INITIALIZE SESSION STATES FOR 2-WAY SYNC ---
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 8
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 40} for i in range(1, 9)]
    slots.insert(4, {"Slot": "LUNCH BREAK", "Duration (Mins)": 40})
    st.session_state.periods_timing_df = pd.DataFrame(slots)

if "classes_df" not in st.session_state: 
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["1st A", "1st B", "6th A"]})
if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame({
        "Teacher Name": ["Mr. Rohan Das", "Coach Ravi", "Mrs. Anita Sharma"],
        "Subject": ["Maths", "Sports", "English"],
        "Allowed Classes": ["All", "All", "1st A, 1st B"]
    })
if "fixed_rules" not in st.session_state: 
    st.session_state.fixed_rules = []

# --- TAB LAYOUT ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🕒 1. Timings & Days", 
    "🏫 2. Classes", 
    "👨‍🏫 3. Teachers", 
    "⚙️ 4. Rules", 
    "🚀💬 5. AI Co-Pilot & Engine"
])

# ==========================================
# TABS 1-4 (SYNCED WITH AI UI)
# ==========================================
with tab1:
    st.header("Weekly Schedule & Periods Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.working_days = st.number_input("Working Days per Week (e.g., Mon-Sat = 6)", min_value=1, max_value=7, value=int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("Periods per Day", min_value=1, max_value=20, value=int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch Break happens AFTER which period?", min_value=1, max_value=15, value=int(st.session_state.break_at))
    
    with col2:
        st.write("Custom Period Durations:")
        st.session_state.periods_timing_df = st.data_editor(st.session_state.periods_timing_df, use_container_width=True, hide_index=True)

with tab2:
    st.header("Classes Configuration")
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.header("Teachers & Subject Mapping")
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.header("Fixed Rules & Conditions")
    st.json(st.session_state.fixed_rules)

# ==========================================
# TAB 5: UNIFIED DASHBOARD (CHAT + ENGINE)
# ==========================================
with tab5:
    col_chat, col_engine = st.columns([4, 6], gap="large")
    
    # ------------------------------------------
    # LEFT COLUMN: AI CO-PILOT CHAT
    # ------------------------------------------
    with col_chat:
        col_c1, col_c2 = st.columns([7, 3])
        with col_c1:
            st.subheader("💬 AI Co-Pilot")
        with col_c2:
            if st.button("🗑️ Clear Chat"):
                del st.session_state["chat_messages"]
                st.rerun()

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {
                    "role": "system", 
                    "content": (
                        "You are a strict Timetable Data Collector.\n"
                        "Extract and summarize the user's data EXACTLY into these 8 points:\n"
                        "1. Working days per week & School timing\n"
                        "2. Total periods per day\n"
                        "3. Lunch break (after which period)\n"
                        "4. Total classes plus sections\n"
                        "5. Total subjects\n"
                        "6. Total teacher (A. Naam, B. Subject, C. Classes)\n"
                        "7. Total other activity and curriculum\n"
                        "8. Total rules\n\n"
                        "PROCESS:\n"
                        "If user sends data in PARTS, acknowledge it and wait for the rest.\n"
                        "Map the prompt to these 8 points mentally and present them clearly.\n"
                        "If you find any CONTRADICTION, DO NOT stop the process. Just write the contradiction at the end under '⚠️ Contradictions Found'.\n"
                        "End with: 'Agar data complete hai, toh Sync dabayein'."
                    )
                },
                {
                    "role": "assistant", 
                    "content": "Namaste Sandeep Sir! Main aapka naya Data Collector hoon. Data ko lamba hone par Part 1, Part 2 me dein. Main isko in 8 points me nikalunga:\n1. Timing & Days\n2. Periods\n3. Lunch break\n4. Classes + Sections\n5. Subjects\n6. Teachers (Naam, Subject, Classes)\n7. Activity\n8. Rules"
                }
            ]

        chat_container = st.container(height=550)
        
        with chat_container:
            for message in st.session_state.chat_messages:
                if message["role"] != "system":
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        if prompt := st.chat_input("Apna instruction yahan likhein..."):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            if not client:
                st.error("❌ Groq API Key missing!")
            else:
                with st.spinner("AI 8 points extract kar raha hai..."):
                    try:
                        messages_to_send = [st.session_state.chat_messages[0]]
                        if len(st.session_state.chat_messages) > 7:
                            messages_to_send.extend(st.session_state.chat_messages[-6:])
                        else:
                            messages_to_send.extend(st.session_state.chat_messages[1:])
                            
                        completion = client.chat.completions.create(
                            model="llama-3.1-8b-instant",  
                            messages=messages_to_send,
                            temperature=0.3,
                            max_tokens=450 
                        )
                        
                        response = completion.choices[0].message.content
                        
                        with chat_container:
                            with st.chat_message("assistant"):
                                st.markdown(response)
                        
                        st.session_state.chat_messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        st.error(f"Error connecting to Groq API: {e}")

    # ------------------------------------------
    # RIGHT COLUMN: GENERATION ENGINE
    # ------------------------------------------
    with col_engine:
        st.subheader("⚙️ Action Center & Engine")
        
        if st.button("🔄 1. Sync AI Rules from Chat", use_container_width=True):
            if not client:
                st.error("Groq API Key missing!")
            elif "chat_messages" not in st.session_state or len(st.session_state.chat_messages) <= 2:
                st.warning("⚠️ Pehle AI se kuch rules discuss karein (Left side mein)!")
            else:
                with st.spinner("Translating 8-Point Data into UI Format..."):
                    clean_history = []
                    for msg in st.session_state.chat_messages:
                        if msg["role"] == "user":
                            clean_history.append(f"User Part: {msg['content']}")
                    
                    chat_history = "\n".join(clean_history[-5:])

                    extraction_prompt = (
                        "Extract the user's timetable data into JSON based on the 8 points discussed.\n"
                        'Format EXACTLY like this JSON:\n'
                        '{"working_days":6,"periods_per_day":8,"break_at":4,"classes":["1st A", "1st B"],"teachers":[{"Teacher Name":"Balram","Subject":"Sanskrit","Allowed Classes":"1st A"}],"fixed_rules":[]}\n\n'
                        "Data to parse:\n" + chat_history
                    )
                    
                    try:
                        completion = client.chat.completions.create(
                            model="llama-3.1-8b-instant",  
                            messages=[{"role": "user", "content": extraction_prompt}],
                            temperature=0.1,
                            response_format={"type": "json_object"},
                            max_tokens=1500 
                        )
                        
                        raw_output = completion.choices[0].message.content
                        
                        # [THE FIX: Syntax Error Proof Markdown Stripper using Math Logic]
                        clean_output = raw_output.strip()
                        bt = chr(96) * 3  # Creates ``` without writing it as a string literal
                        if clean_output.startswith(bt + "json"):
                            clean_output = clean_output[7:]
                        elif clean_output.startswith(bt):
                            clean_output = clean_output[3:]
                        if clean_output.endswith(bt):
                            clean_output = clean_output[:-3]
                                
                        extracted_data = json.loads(clean_output.strip())
                        
                        st.session_state.working_days = int(max(1, min(7, extracted_data.get("working_days", 6))))
                        st.session_state.periods_per_day = int(max(1, min(20, extracted_data.get("periods_per_day", 8))))
                        st.session_state.break_at = int(max(1, min(15, extracted_data.get("break_at", 4))))
                        
                        if "classes" in extracted_data:
                            st.session_state.classes_df = pd.DataFrame({"Class Name": extracted_data["classes"]})
                        if "teachers" in extracted_data:
                            st.session_state.teachers_df = pd.DataFrame(extracted_data["teachers"])
                            
                        st.session_state.fixed_rules = extracted_data.get("fixed_rules", [])
                        st.success("✅ Rules Synced! Check Tabs 1-4. Now click Generate.")
                        st.rerun()
                    except json.decoder.JSONDecodeError as je:
                        st.error(f"⚠️ JSON Parsing Error: AI ne aadha JSON bheja ya format galat kar diya. (Error: {je})\nKoshish karein thoda data kam karke ya clear karke bhejein.")
                    except Exception as e:
                        st.error(f"Failed to extract rules: {e}")
                        
        st.markdown("---")
        
        if st.button("🚀 2. Run Weekly Engine & Generate", type="primary", use_container_width=True):
            with st.spinner("Analyzing requirements & Running Weekly engines..."):
                sys.setrecursionlimit(5000)
                
                classes_list = st.session_state.classes_df["Class Name"].dropna().tolist()
                teachers_list = st.session_state.teachers_df.to_dict('records')
                periods_per_day = st.session_state.periods_per_day
                working_days = st.session_state.working_days
                break_at = st.session_state.break_at
                fixed_rules = st.session_state.fixed_rules
                
                # --- WEEKLY GRID GENERATION ---
                days_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                period_labels = []
                valid_periods = []
                global_p_idx = 0
                
                for d in range(working_days):
                    day_name = days_str[d]
                    for i in range(1, periods_per_day + 1):
                        global_p_idx += 1
                        period_labels.append(f"{day_name} - P{i}")
                        valid_periods.append(global_p_idx)
                        
                        if i == break_at:
                            period_labels.append(f"{day_name} - LUNCH")
                
                total_weekly_periods = len(valid_periods)
                
                initial_timetable = {c: ["Free"] * len(period_labels) for c in classes_list} 
                for c in classes_list:
                    for idx, label in enumerate(period_labels):
                        if "LUNCH" in label:
                            initial_timetable[c][idx] = "LUNCH / BREAK"
                            
                initial_busy_teachers = {i: set() for i in range(len(period_labels))}
                
                # --- GATHER REQUIREMENTS ---
                class_requirements = {c: [] for c in classes_list}
                for t in teachers_list:
                    t_name = t.get("Teacher Name", "")
                    t_sub_raw = str(t.get("Subject", ""))
                    t_allowed_str = str(t.get("Allowed Classes", "")).strip()
                    
                    if t_allowed_str.lower() == "all" or t_allowed_str == "":
                        allowed_classes = classes_list
                    else:
                        allowed_classes = [x.strip() for x in t_allowed_str.split(",")]
                    
                    for c in allowed_classes:
                        if c in classes_list:
                            for sub in [s.strip() for s in t_sub_raw.split(",")]:
                                class_requirements[c].append((t_name, sub))

                # Pad Activity Master if missing
                for c in classes_list:
                    has_activity = any("activity" in sub.lower() for t, sub in class_requirements[c])
                    if not has_activity:
                        class_requirements[c].append(("Activity Master", "Activity"))

                # --- NEW WEEKLY SANITY CHECK ---
                teacher_global_load = {}
                for c in classes_list:
                    for t_name, sub in class_requirements[c]:
                        teacher_global_load[t_name] = teacher_global_load.get(t_name, 0) + 1
                
                sanity_errors = []
                for t_name,
