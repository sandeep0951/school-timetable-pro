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
st.set_page_config(page_title="Advanced Timetable Pro (Hybrid Edition)", layout="wide")

# Initialize Groq Client
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_api_key)
except:
    client = None

# App Header
st.title("🏫 Advanced Timetable Pro (Hybrid 2-Tier Engine)")
st.markdown("Tier 1: Custom Python Logic | Tier 2: Google OR-Tools Fallback")

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

# --- TAB LAYOUT ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🕒 1. Timings & Periods", 
    "🏫 2. Classes & Subjects", 
    "👨‍🏫 3. Teachers & Rules", 
    "⚙️ 4. Extra Conditions", 
    "🚀 5. Generate (Hybrid)",
    "💬 6. AI Co-Pilot"
])

# ==========================================
# TABS 1-4 (SYNCED WITH AI UI)
# ==========================================
with tab1:
    st.header("School Timings & Periods Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.num_periods = st.number_input("Total Number of Periods", min_value=1, max_value=20, value=st.session_state.num_periods)
        st.session_state.break_at = st.number_input("Break happens AFTER which period?", min_value=1, max_value=15, value=st.session_state.break_at)
    
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
# TAB 5: THE HYBRID ENGINE (CUSTOM -> OR-TOOLS)
# ==========================================
with tab5:
    st.header("Hybrid Timetable Generation")
    
    if st.button("🔄 Sync AI Rules to UI Tabs"):
        if not client:
            st.error("Groq API Key missing!")
        elif "chat_messages" not in st.session_state or len(st.session_state.chat_messages) <= 2:
            st.warning("⚠️ Pehle Tab 6 mein AI se kuch rules discuss karein!")
        else:
            with st.spinner("Translating Chat History into UI Data..."):
                chat_history = str(st.session_state.chat_messages)
                extraction_prompt = '''Extract ALL timetable rules, teachers, durations, and classes from the chat history into a strict JSON format. 
                ONLY output JSON. Format MUST be exactly:
                {
                    "num_periods": 7,
                    "break_at": 3,
                    "durations": [{"Slot": "Period 1", "Duration (Mins)": 50}],
                    "classes": ["6th A", "6th B", "7th", "8th", "9th", "10th"],
                    "teachers": [
                        {"Teacher Name": "Balram", "Subject": "Sanskrit", "Allowed Classes": "6th A, 6th B, 7th"}
                    ],
                    "fixed_rules": [
                        {"period": 1, "class": "10th", "subject": "Maths", "teacher": "Nikum"}
                    ]
                }
                CRITICAL INSTRUCTIONS: 
                1. If a teacher teaches MULTIPLE subjects, create SEPARATE rows.
                2. YOU MUST INCLUDE "Activity" subject and its teacher if discussed! Do not skip it.
                Chat History: ''' + chat_history
                
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": extraction_prompt}],
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    extracted_data = json.loads(completion.choices[0].message.content)
                    
                    st.session_state.num_periods = extracted_data.get("num_periods", 7)
                    st.session_state.break_at = extracted_data.get("break_at", 3)
                    
                    if "durations" in extracted_data:
                        st.session_state.periods_timing_df = pd.DataFrame(extracted_data["durations"])
                    if "classes" in extracted_data:
                        st.session_state.classes_df = pd.DataFrame({"Class Name": extracted_data["classes"]})
                    if "teachers" in extracted_data:
                        st.session_state.teachers_df = pd.DataFrame(extracted_data["teachers"])
                        
                    st.session_state.fixed_rules = extracted_data.get("fixed_rules", [])
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to extract rules: {e}")
                    
    st.markdown("---")
    st.subheader("⚙️ 2. Run Hybrid Engine (Custom Python ➡️ Google OR-Tools)")
    
    if st.button("🚀 Run Hybrid Engine & Generate", type="primary"):
        with st.spinner("Processing Hybrid Engine... (Giving Tier 1 up to 20 seconds)"):
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
            
            # --- COMMON STEP 1: GATHER REQUIREMENTS ---
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

            # Activity Rule
            for c in classes_list:
                has_activity = any("activity" in sub.lower() for t, sub in class_requirements[c])
                if not has_activity:
                    class_requirements[c].append(("Activity Master", "Activity"))

            teacher_workload = {t.get("Teacher Name", ""): 0 for t in teachers_list}
            teacher_workload["Activity Master"] = 0
            teacher_workload["Library Master"] = 0
            
            for c in classes_list:
                for t_name, sub in class_requirements[c]:
                    teacher_workload[t_name] = teacher_workload.get(t_name, 0) + 1

            # Padding
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

            # Apply Fixed Rules to initial state
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

            # ==========================================
            # TIER 1: CUSTOM PYTHON ENGINE
            # ==========================================
            st.info("🔄 Tier 1: Trying Custom Python Engine (Giving it 20 seconds)...")
            
            custom_timetable = copy.deepcopy(initial_timetable)
            custom_busy = copy.deepcopy(initial_busy_teachers)
            custom_reqs = copy.deepcopy(class_requirements)
            custom_start_time = time_module.time()
            
            def solve_custom(p_idx, c_idx):
                # Increased timeout to 20 seconds!
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
                        # OMNIPRESENT LIBRARY MASTER FIX
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
                    if t_name != "Library Master": # Prevent set key error
                        custom_busy[p_idx].remove(t_name)
                    custom_reqs[c].append(req) 
                
                return False

            custom_success = solve_custom(0, 0)
            
            if custom_success:
                df = pd.DataFrame(custom_timetable)
                df.insert(0, "Time / Period", period_labels)
                st.success(f"✅ Tier 1 Success: Timetable generated using Custom Python Engine! (Took {round(time_module.time() - custom_start_time, 2)} seconds)")
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            # ==========================================
            # TIER 2: GOOGLE OR-TOOLS FALLBACK
            # ==========================================
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
                            # OMNIPRESENT LIBRARY MASTER FIX
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
                        st.error("❌ ABSOLUTE DEADLOCK! Even Google OR-Tools could not solve this mathematically. You MUST relax constraints or add teachers.")

# ==========================================
# TAB 6: AI Co-Pilot
# ==========================================
with tab6:
    st.header("💬 AI Co-Pilot (Data Collector)")
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "system", 
                "content": '''You are Sandeep's Data Extractor. CRITICAL RULES: 1. NEVER GENERATE A TIMETABLE. 2. Your job is to listen and say: "Maine rules note kar liye hain. Tab 5 mein 'Sync AI Rules' dabayein."'''
            },
            {
                "role": "assistant", 
                "content": "Namaste Sandeep Sir! Main aapka AI Assistant hoon. Mujhe apne rules bataiye, main unhe extract karke aage Tabs mein bhej dunga."
            }
        ]

    for message in st.session_state.chat_messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Apna instruction yahan likhein..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.chat_messages.append({"role": "user", "content": prompt})

        if not client:
            st.error("❌ Groq API Key missing!")
        else:
            with st.spinner("AI is understanding your rules..."):
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=st.session_state.chat_messages,
                        temperature=0.1, 
                    )
                    
                    response = completion.choices[0].message.content
                    
                    with st.chat_message("assistant"):
                        st.markdown(response)
                    
                    st.session_state.chat_messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"Error connecting to Groq API: {e}")
