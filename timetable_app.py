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
st.set_page_config(page_title="Advanced Timetable Pro (Unified Edition)", layout="wide")

# Initialize Groq Client
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_api_key)
except:
    client = None

# App Header
st.title("🏫 Advanced Timetable Pro (Unified Engine Dashboard)")
st.markdown("Tier 1: Custom Python Logic | Tier 2: Google OR-Tools | AI Assistant")

if not ORTOOLS_AVAILABLE:
    st.warning("⚠️ Google 'ortools' is not installed. The app will only use the Custom Python Engine. Add 'ortools' to requirements.txt for the enterprise fallback.")

# --- INITIALIZE SESSION STATES FOR 2-WAY SYNC ---
if "num_periods" not in st.session_state: st.session_state.num_periods = 7
if "break_at" not in st.session_state: st.session_state.break_at = 3
if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 50 if i==1 else 45} for i in range(1, 8)]
    slots.insert(3, {"Slot": "LUNCH BREAK", "Duration (Mins)": 15})
    st.session_state.periods_timing_df = pd.DataFrame(slots)

if "classes_df" not in st.session_state: 
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["6th A", "6th B", "7th", "8th", "9th", "10th"]})
if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame({
        "Teacher Name": ["Nikum", "Dipendra", "Activity Master"],
        "Subject": ["Maths", "English", "Activity"],
        "Allowed Classes": ["9th, 10th", "9th, 10th", "All"]
    })
if "fixed_rules" not in st.session_state: 
    st.session_state.fixed_rules = []

# --- TAB LAYOUT (REDUCED TO 5 TABS) ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🕒 1. Timings", 
    "🏫 2. Classes", 
    "👨‍🏫 3. Teachers", 
    "⚙️ 4. Rules", 
    "🚀💬 5. AI Co-Pilot & Engine"
])

# ==========================================
# TABS 1-4 (SYNCED WITH AI UI)
# ==========================================
with tab1:
    st.header("School Timings & Periods Configuration")
    col1, col2 = st.columns(2)
    with col1:
        # [BUG FIX: SAFE CLAMPING] Make sure values never exceed limits
        safe_periods = int(max(1, min(20, st.session_state.num_periods)))
        st.session_state.num_periods = st.number_input("Total Number of Periods", min_value=1, max_value=20, value=safe_periods)
        
        safe_break = int(max(1, min(15, st.session_state.break_at)))
        st.session_state.break_at = st.number_input("Break happens AFTER which period?", min_value=1, max_value=15, value=safe_break)
    
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
                        "You are Sandeep's Timetable Data Validator.\n"
                        "NEVER GENERATE TIMETABLES. Just validate data.\n"
                        "PROCESS: Ensure Total Periods, Break, Classes, Teachers, and Rules exist. "
                        "Reject if a teacher takes more classes than Total Periods. Be concise in mix of Hindi/English."
                    )
                },
                {
                    "role": "assistant", 
                    "content": "Namaste Sandeep Sir! Apna timetable ka data (Classes, Teachers, Periods, Rules) daaliye. Main check karunga."
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
                with st.spinner("AI is thinking..."):
                    try:
                        # [SMART BALANCED MEMORY FOR CHAT]
                        messages_to_send = [st.session_state.chat_messages[0]]
                        if len(st.session_state.chat_messages) > 5:
                            messages_to_send.extend(st.session_state.chat_messages[-4:])
                        else:
                            messages_to_send.extend(st.session_state.chat_messages[1:])
                            
                        completion = client.chat.completions.create(
                            model="llama-3.1-8b-instant",  
                            messages=messages_to_send,
                            temperature=0.3, 
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
                with st.spinner("Translating Chat History into UI Data..."):
                    clean_history = []
                    for msg in st.session_state.chat_messages:
                        if msg["role"] != "system":
                            clean_history.append(f"{msg['role'].capitalize()}: {msg['content']}")
                    
                    chat_history = "\n".join(clean_history[-6:])

                    extraction_prompt = (
                        "Extract timetable data to JSON strictly based on the provided conversation.\n"
                        'Format EXACTLY like this:\n'
                        '{"num_periods":8,"break_at":4,"durations":[{"Slot":"Period 1","Duration (Mins)":50}],"classes":["6th A"],"teachers":[{"Teacher Name":"Balram","Subject":"Sanskrit","Allowed Classes":"6th A"}],"fixed_rules":[]}\n\n'
                        "Data:\n" + chat_history
                    )
                    
                    try:
                        completion = client.chat.completions.create(
                            model="llama-3.1-8b-instant",  
                            messages=[{"role": "user", "content": extraction_prompt}],
                            temperature=0.1,
                            response_format={"type": "json_object"}
                        )
                        extracted_data = json.loads(completion.choices[0].message.content)
                        
                        # [BUG FIX: SAFE CLAMPING FOR JSON PARSING]
                        raw_periods = extracted_data.get("num_periods", 7)
                        st.session_state.num_periods = int(max(1, min(20, raw_periods)))
                        
                        raw_break = extracted_data.get("break_at", 3)
                        st.session_state.break_at = int(max(1, min(15, raw_break)))
                        
                        if "durations" in extracted_data:
                            st.session_state.periods_timing_df = pd.DataFrame(extracted_data["durations"])
                        if "classes" in extracted_data:
                            st.session_state.classes_df = pd.DataFrame({"Class Name": extracted_data["classes"]})
                        if "teachers" in extracted_data:
                            st.session_state.teachers_df = pd.DataFrame(extracted_data["teachers"])
                            
                        st.session_state.fixed_rules = extracted_data.get("fixed_rules", [])
                        st.success("✅ Rules Synced! Check Tabs 1-4. Now click Generate.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to extract rules: {e}")
                        
        st.markdown("---")
        
        if st.button("🚀 2. Run Hybrid Engine & Generate", type="primary", use_container_width=True):
            with st.spinner("Analyzing requirements & Running engines..."):
                sys.setrecursionlimit(5000)
                
                classes_list = st.session_state.classes_df["Class Name"].dropna().tolist()
                teachers_list = st.session_state.teachers_df.to_dict('records')
                periods_count = st.session_state.num_periods
                break_at = st.session_state.break_at
                fixed_rules = st.session_state.fixed_rules
                
                period_labels = []
                p_idx = 0
                valid_periods = []
                
                for i in range(1, periods_count + 2):
                    if i == break_at + 1:
                        period_labels.append("BREAK")
                    else:
                        p_idx += 1
                        period_labels.append(f"Period {p_idx}")
                        valid_periods.append(i)
                
                initial_timetable = {c: ["Free"] * len(period_labels) for c in classes_list} 
                for c in classes_list:
                    initial_timetable[c][break_at] = "LUNCH / BREAK"
                    
                initial_busy_teachers = {i: set() for i in range(len(period_labels))}
                
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

                for c in classes_list:
                    has_activity = any("activity" in sub.lower() for t, sub in class_requirements[c])
                    if not has_activity:
                        class_requirements[c].append(("Activity Master", "Activity"))

                teacher_global_load = {}
                for c in classes_list:
                    for t_name, sub in class_requirements[c]:
                        teacher_global_load[t_name] = teacher_global_load.get(t_name, 0) + 1
                
                sanity_failed = False
                for t_name, load in teacher_global_load.items():
                    if t_name not in ["Library Master"] and load > periods_count:
                        st.error(f"🛑 PHYSICAL IMPOSSIBILITY DETECTED:\nTeacher **'{t_name}'** is required in **{load} classes**, but there are only **{periods_count} periods** in the day!")
                        st.info(f"💡 You can type this error directly to the AI Co-Pilot on the left to ask for a solution.")
                        sanity_failed = True
                
                if sanity_failed:
                    st.stop()

                teacher_workload = {t.get("Teacher Name", ""): 0 for t in teachers_list}
                teacher_workload["Activity Master"] = 0
                teacher_workload["Library Master"] = 0
                
                for c in classes_list:
                    for t_name, sub in class_requirements[c]:
                        teacher_workload[t_name] = teacher_workload.get(t_name, 0) + 1

                for c in classes_list:
                    while len(class_requirements[c]) < periods_count:
                        valid_pad_options = []
                        for t_name, sub in set(class_requirements[c]): 
                            if t_name not in ["Library Master", "Activity Master"] and teacher_workload.get(t_name, 0) < periods_count - 1:
                                valid_pad_options.append((t_name, f"{sub} (Rev)"))
                        
                        if valid_pad_options:
                            chosen = random.choice(valid_pad_options)
                            class_requirements[c].append(chosen)
                            teacher_workload[chosen[0]] += 1
                        else:
                            class_requirements[c].append(("Library Master", "Library/Self-Study"))
                            teacher_workload["Library Master"] += 1
                    
                    if len(class_requirements[c]) > periods_count:
                        class_requirements[c] = class_requirements[c][:periods_count]

                for rule in fixed_rules:
                    p = rule.get("period", 1)
                    c = rule.get("class", "")
                    sub = rule.get("subject", "")
                    teacher = rule.get("teacher", "")
                    row_idx = p - 1 if p <= break_at else p
                    if c in classes_list and row_idx < len(period_labels):
                        initial_timetable[c][row_idx] = f"{sub} ({teacher})"
                        initial_busy_teachers[row_idx].add(teacher)
                        req_tuple = (teacher, sub)
                        if req_tuple in class_requirements[c]:
                            class_requirements[c].remove(req_tuple)

                st.info("🔄 Tier 1: Running Custom Python Engine (Max 20s)...")
                
                custom_timetable = copy.deepcopy(initial_timetable)
                custom_busy = copy.deepcopy(initial_busy_teachers)
                custom_reqs = copy.deepcopy(class_requirements)
                custom_start_time = time_module.time()
                
                def solve_custom(p_idx, c_idx):
                    if time_module.time() - custom_start_time > 20.0: return False
                    if p_idx >= len(period_labels): return True
                    if "BREAK" in period_labels[p_idx]: return solve_custom(p_idx + 1, 0)
                    
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
                            if req[0] not in custom_busy[p_idx] or req[0] == "Library Master":
                                valid_reqs.append(req)
                    
                    random.shuffle(valid_reqs) 
                    
                    for req in valid_reqs:
                        t_name, sub = req
                        custom_timetable[c][p_idx] = f"{sub} ({t_name})"
                        custom_busy[p_idx].add(t_name)
                        custom_reqs[c].remove(req) 
                        
                        if solve_custom(next_p_idx, next_c_idx): return True
                        
                        custom_timetable[c][p_idx] = "Free"
                        if t_name != "Library Master": 
                            custom_busy[p_idx].remove(t_name)
                        custom_reqs[c].append(req) 
                    
                    return False

                custom_success = solve_custom(0, 0)
                
                if custom_success:
                    df = pd.DataFrame(custom_timetable)
                    df.insert(0, "Time / Period", period_labels)
                    st.success(f"✅ Tier 1 Success: Timetable generated using Custom Python Engine! (Took {round(time_module.time() - custom_start_time, 2)} seconds)")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                
                else:
                    st.warning("⚠️ Custom Engine timed out after 20 seconds. Falling back to Tier 2 (Google OR-Tools)...")
                    
                    if not ORTOOLS_AVAILABLE:
                        st.error("❌ Fallback Failed: Google 'ortools' is not installed. Please add it to requirements.txt.")
                    else:
                        ortools_timetable = copy.deepcopy(initial_timetable)
                        ortools_reqs = copy.deepcopy(class_requirements)
                        
                        model = cp_model.CpModel()
                        x = {} 
                        
                        for c in classes_list:
                            x[c] = {}
                            for p in valid_periods:
                                x[c][p] = {}
                                for r_idx in range(len(ortools_reqs[c])):
                                    x[c][p][r_idx] = model.NewBoolVar(f'assign_{c}_{p}_{r_idx}')

                        for c in classes_list:
                            for p in valid_periods:
                                model.AddExactlyOne([x[c][p][r_idx] for r_idx in range(len(ortools_reqs[c]))])

                        for c in classes_list:
                            for r_idx in range(len(ortools_reqs[c])):
                                model.AddExactlyOne([x[c][p][r_idx] for p in valid_periods])

                        all_teachers = set()
                        for c in classes_list:
                            for t_name, sub in ortools_reqs[c]:
                                if t_name != "Library Master":
                                    all_teachers.add(t_name)

                        for p in valid_periods:
                            for teacher in all_teachers:
                                teacher_assignments_in_period = []
                                for c in classes_list:
                                    for r_idx, req in enumerate(ortools_reqs[c]):
                                        if req[0] == teacher:
                                            teacher_assignments_in_period.append(x[c][p][r_idx])
                                if len(teacher_assignments_in_period) > 1:
                                    model.AddAtMostOne(teacher_assignments_in_period)

                        for rule in fixed_rules:
                            p_val = rule.get("period", 1)
                            c_val = rule.get("class", "")
                            t_val = rule.get("teacher", "")
                            actual_p = p_val if p_val <= break_at else p_val + 1
                            
                            if c_val in classes_list and actual_p in valid_periods:
                                for r_idx, req in enumerate(ortools_reqs[c_val]):
                                    if req[0] == t_val:
                                        model.Add(x[c_val][actual_p][r_idx] == 1)
                                        break

                        solver = cp_model.CpSolver()
                        solver.parameters.max_time_in_seconds = 15.0 
                        status = solver.Solve(model)

                        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                            for c in classes_list:
                                for p in valid_periods:
                                    for r_idx, req in enumerate(ortools_reqs[c]):
                                        if solver.Value(x[c][p][r_idx]) == 1:
                                            p_idx = p - 1
                                            ortools_timetable[c][p_idx] = f"{req[1]} ({req[0]})"
                                            
                            df = pd.DataFrame(ortools_timetable)
                            df.insert(0, "Time / Period", period_labels)
                            
                            st.success(f"✅ Tier 2 Success: Timetable generated using Google OR-Tools! (Status: {solver.StatusName(status)})")
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.error("❌ ABSOLUTE DEADLOCK! The remaining constraints are too tight to solve mathematically.")
                            st.info("💡 Pucho AI se (left side): 'Bhai deadlock aa raha hai, kaise theek karun?'")
