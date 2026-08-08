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

st.set_page_config(page_title="Advanced Timetable Pro", layout="wide")

try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_api_key)
except:
    client = None

st.title("🏫 Advanced Timetable Pro (Weekly Engine + 8-Point AI)")

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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🕒 1. Timings & Days", "🏫 2. Classes", "👨‍🏫 3. Teachers", "⚙️ 4. Rules", "🚀💬 5. AI Co-Pilot & Engine"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.working_days = st.number_input("Working Days per Week", min_value=1, max_value=7, value=int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("Periods per Day", min_value=1, max_value=20, value=int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch Break AFTER period?", min_value=1, max_value=15, value=int(st.session_state.break_at))
    with col2:
        st.session_state.periods_timing_df = st.data_editor(st.session_state.periods_timing_df, use_container_width=True, hide_index=True)

with tab2:
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.json(st.session_state.fixed_rules)

with tab5:
    col_chat, col_engine = st.columns([4, 6], gap="large")
    
    with col_chat:
        col_c1, col_c2 = st.columns([7, 3])
        with col_c1: st.subheader("💬 AI Co-Pilot")
        with col_c2:
            if st.button("🗑️ Clear Chat"):
                del st.session_state["chat_messages"]
                st.rerun()

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "system", "content": "You are a strict Timetable Data Collector. Extract data into 8 points. Wait for chunks if needed. Mention contradictions at the end. Be concise."},
                {"role": "assistant", "content": "Namaste Sandeep Sir! Apna data daaliye. Main isko in 8 points me extract karunga:"}
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
                with st.chat_message("user"): st.markdown(prompt)

            if not client: st.error("❌ Groq API Key missing!")
            else:
                with st.spinner("AI Soch raha hai..."):
                    try:
                        messages_to_send = [st.session_state.chat_messages[0]]
                        if len(st.session_state.chat_messages) > 3:
                            messages_to_send.extend(st.session_state.chat_messages[-2:])
                        else:
                            messages_to_send.extend(st.session_state.chat_messages[1:])
                            
                        complete_response = ""
                        for step in range(5): 
                            try:
                                completion = client.chat.completions.create(
                                    model="llama-3.1-8b-instant",  
                                    messages=messages_to_send,
                                    temperature=0.3,
                                    max_tokens=800
                                )
                                chunk = completion.choices[0].message.content
                                finish_reason = completion.choices[0].finish_reason
                                complete_response += chunk
                                
                                if finish_reason == "length":
                                    time_module.sleep(5) 
                                    messages_to_send.append({"role": "assistant", "content": chunk})
                                    messages_to_send.append({"role": "user", "content": "Continue."})
                                else:
                                    break 
                            except Exception as api_err:
                                time_module.sleep(30)
                                continue 
                                    
                        if complete_response:
                            with chat_container:
                                with st.chat_message("assistant"): st.markdown(complete_response)
                            st.session_state.chat_messages.append({"role": "assistant", "content": complete_response})
                            st.rerun()
                    except Exception as e:
                        st.error(f"System Error: {e}")

    with col_engine:
        st.subheader("⚙️ Action Center & Engine")
        
        if st.button("🔄 1. Sync AI Rules from Chat", use_container_width=True):
            if not client: st.error("Groq API Key missing!")
            else:
                with st.spinner("Translating Data..."):
                    clean_history = [f"User: {msg['content']}" for msg in st.session_state.chat_messages if msg["role"] == "user"]
                    chat_history = "\n".join(clean_history[-2:])
                    
                    extraction_prompt = (
                        "Extract the user's timetable data into JSON based on the 8 points discussed.\n"
                        '{"working_days":6,"periods_per_day":8,"break_at":4,"classes":["1st A", "1st B"],"teachers":[{"Teacher Name":"Balram","Subject":"Sanskrit","Allowed Classes":"1st A"}],"fixed_rules":[]}\n\n'
                        "Data to parse:\n" + chat_history
                    )
                    
                    extracted_data = None
                    for step in range(3):
                        try:
                            completion = client.chat.completions.create(
                                model="llama-3.1-8b-instant",  
                                messages=[{"role": "user", "content": extraction_prompt}],
                                temperature=0.1,
                                response_format={"type": "json_object"},
                                max_tokens=2500 
                            )
                            raw_output = completion.choices[0].message.content
                            clean_output = raw_output.strip()
                            bt = chr(96) * 3  
                            if clean_output.startswith(bt + "json"): clean_output = clean_output[7:]
                            elif clean_output.startswith(bt): clean_output = clean_output[3:]
                            if clean_output.endswith(bt): clean_output = clean_output[:-3]
                                    
                            extracted_data = json.loads(clean_output.strip())
                            break
                        except Exception as e:
                            time_module.sleep(5)
                            continue
                    
                    if extracted_data:
                        st.session_state.working_days = int(max(1, min(7, extracted_data.get("working_days", 6))))
                        st.session_state.periods_per_day = int(max(1, min(20, extracted_data.get("periods_per_day", 8))))
                        st.session_state.break_at = int(max(1, min(15, extracted_data.get("break_at", 4))))
                        if "classes" in extracted_data: st.session_state.classes_df = pd.DataFrame({"Class Name": extracted_data["classes"]})
                        if "teachers" in extracted_data: st.session_state.teachers_df = pd.DataFrame(extracted_data["teachers"])
                        st.session_state.fixed_rules = extracted_data.get("fixed_rules", [])
                        st.success("✅ Rules Synced!")
                        st.rerun()

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
                
                days_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                period_labels = []
                valid_periods = []
                global_p_idx = 0
                
                # --- FIX 1: SATURDAY HALF DAY & NO LUNCH ---
                for d in range(working_days):
                    day_name = days_str[d]
                    # If Saturday, only 4 periods
                    current_day_periods = 4 if day_name.lower() == "saturday" else periods_per_day
                    
                    for i in range(1, current_day_periods + 1):
                        global_p_idx += 1
                        period_labels.append(f"{day_name} - P{i}")
                        valid_periods.append(global_p_idx)
                        
                        # No lunch on Saturday
                        if i == break_at and day_name.lower() != "saturday": 
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
                    allowed_classes = classes_list if (t_allowed_str.lower() == "all" or t_allowed_str == "") else [x.strip() for x in t_allowed_str.split(",")]
                    for c in allowed_classes:
                        if c in classes_list:
                            for sub in [s.strip() for s in t_sub_raw.split(",")]:
                                class_requirements[c].append((t_name, sub))

                # --- FIX 2: REMOVE ACTIVITY MASTER HARDCODING ---
                # (Removed the explicit Activity Master injection loop here)

                # --- FIX 3: FIX PADDING SPAM (NO MORE REV REV REV) ---
                # Padding requirements to fill the WEEK simply with Free/Library
                for c in classes_list:
                    while len(class_requirements[c]) < total_weekly_periods:
                        class_requirements[c].append(("Self-Study / Free", "Library"))
                    
                    if len(class_requirements[c]) > total_weekly_periods:
                        class_requirements[c] = class_requirements[c][:total_weekly_periods]

                st.info(f"🔄 Tier 1: Running Custom Python Engine for {working_days} Days ({total_weekly_periods} valid periods)...")
                
                custom_timetable = copy.deepcopy(initial_timetable)
                custom_busy = copy.deepcopy(initial_busy_teachers)
                custom_reqs = copy.deepcopy(class_requirements)
                custom_start_time = time_module.time()
                
                def solve_custom(p_idx, c_idx):
                    if time_module.time() - custom_start_time > 20.0: return False
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
                            if req[0] not in custom_busy[p_idx] or req[0] == "Self-Study / Free":
                                valid_reqs.append(req)
                    
                    random.shuffle(valid_reqs) 
                    
                    for req in valid_reqs:
                        t_name, sub = req
                        custom_timetable[c][p_idx] = f"{sub} ({t_name})"
                        custom_busy[p_idx].add(t_name)
                        custom_reqs[c].remove(req) 
                        if solve_custom(next_p_idx, next_c_idx): return True
                        custom_timetable[c][p_idx] = "Free"
                        if t_name != "Self-Study / Free": custom_busy[p_idx].remove(t_name)
                        custom_reqs[c].append(req) 
                    return False

                custom_success = solve_custom(0, 0)
                
                if custom_success:
                    df = pd.DataFrame(custom_timetable)
                    df.insert(0, "Day / Period", period_labels)
                    st.success("✅ Tier 1 Success: Full Weekly Timetable generated!")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.warning("⚠️ Engine timed out.")
