import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
import json
import random
import sys
import copy
import re

# NAYE AI LIBRARIES
from openai import OpenAI
import anthropic

# Attempt to import Google OR-Tools
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

st.set_page_config(page_title="Advanced Timetable Pro", layout="wide")

# API Keys Setup
try:
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    openai_client = None

try:
    anthropic_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
except:
    anthropic_client = None

st.title("🏫 Advanced Timetable Pro (OpenAI + Claude Edition)")

# ================= STATE INITIALIZATION =================
# TAB 1 States
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 8
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "saturday_half_day" not in st.session_state: st.session_state.saturday_half_day = False 
if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 40} for i in range(1, 9)]
    slots.insert(4, {"Slot": "LUNCH BREAK", "Duration (Mins)": 40})
    st.session_state.periods_timing_df = pd.DataFrame(slots)

# TAB 2 States
if "classes_df" not in st.session_state: 
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["1st A", "1st B"]})

# TAB 3 States
if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame({
        "Teacher Name": ["Mr. Rohan Das", "Coach Ravi"],
        "Subject": ["Maths", "Sports"],
        "Allowed Classes": ["All", "All"],
        "Periods/Week (Per Class)": [6, 4] 
    })

# TAB 4 States (Rules table)
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
        st.session_state.working_days = st.number_input("1. Schedule Weekly (Working Days)", min_value=1, max_value=7, value=int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("2. Period Timing (Periods per Day)", min_value=1, max_value=20, value=int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch Break AFTER period?", min_value=1, max_value=15, value=int(st.session_state.break_at))
        st.session_state.saturday_half_day = st.checkbox("4. Weekend Half Day (Saturday Half-Day)?", value=st.session_state.saturday_half_day)
    with col2:
        st.markdown("**School Timing (Durations):**")
        st.session_state.periods_timing_df = st.data_editor(st.session_state.periods_timing_df, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("**1. Total Classes with Sections:**")
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.markdown("**1, 2, 3, 4: Teachers Name, Subjects, Classes, and Weekly Logic (Periods/Week):**")
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.markdown("**1. Rules from Prompt:**")
    st.session_state.rules_df = st.data_editor(st.session_state.rules_df, num_rows="dynamic", use_container_width=True)

with tab5:
    col_chat, col_engine = st.columns([4, 6], gap="large")
    
    with col_chat:
        col_c1, col_c2 = st.columns([7, 3])
        with col_c1: st.subheader("💬 1. Chat Box")
        with col_c2:
            if st.button("🗑️ Clear Chat"):
                del st.session_state["chat_messages"]
                st.rerun()

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {
                    "role": "system", 
                    "content": (
                        "You are an Expert Timetable Consultant. Your goal is to collect data for 4 Tabs:\n"
                        "Tab 1: Timings (Working days, Periods/day, Break, Weekend rules)\n"
                        "Tab 2: Classes & Sections\n"
                        "Tab 3: Teachers (Name, Subject, Classes, Periods/Week per class)\n"
                        "Tab 4: Rules (Limits, class teacher periods, etc.)\n\n"
                        "When user sends data:\n"
                        "1. Identify which Tab's info was provided.\n"
                        "2. Point out what is STILL MISSING.\n"
                        "3. CRITICAL: Analyze the rules and data. If a teacher's workload is practically impossible or contradicts rules, point it out!\n"
                        "4. Do NOT generate JSON in chat. Just analyze and collect.\n"
                        "5. Once user says 'DONE' or confirms everything is provided, reply EXACTLY: '✅ All data verified! Kripya right side par Sync Button dabayein.'"
                    )
                },
                {"role": "assistant", "content": "Namaste Sandeep Sir! Main aapka Smart Assistant hoon. Kripya apna data bhejein, main Tab 1 se 4 tak sab check karunga aur errors point out karunga."}
            ]

        chat_container = st.container(height=450)
        with chat_container:
            for message in st.session_state.chat_messages:
                if message["role"] != "system":
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        with st.form("chat_input_form", clear_on_submit=True):
            prompt = st.text_area("Apna data yahan paste karein (Fixed size box):", height=120)
            submit_chat = st.form_submit_button("Send 🚀")

        if submit_chat and prompt:
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"): st.markdown(prompt)

            if not openai_client: st.error("❌ OpenAI API Key missing!")
            else:
                with st.spinner("OpenAI is analyzing your data & rules..."):
                    try:
                        chunk_size = 2500
                        prompt_chunks = [prompt[i:i+chunk_size] for i in range(0, len(prompt), chunk_size)]
                        
                        final_ai_reply = ""
                        for c_idx, chunk_text in enumerate(prompt_chunks):
                            messages_to_send = [
                                st.session_state.chat_messages[0],
                                {"role": "user", "content": f"[Data Part {c_idx+1}/{len(prompt_chunks)}]: {chunk_text}\n\nAnalyze this part based on your system instructions."}
                            ]
                            
                            for attempt in range(3):
                                try:
                                    # MODEL 1: OPENAI (Chat & Analysis)
                                    completion = openai_client.chat.completions.create(
                                        model="gpt-4o-mini",  
                                        messages=messages_to_send,
                                        temperature=0.3,
                                        max_tokens=400
                                    )
                                    final_ai_reply += completion.choices[0].message.content + "\n\n"
                                    time_module.sleep(1)
                                    break
                                except Exception as chunk_err:
                                    time_module.sleep(5)
                                    continue
                                        
                        with chat_container:
                            with st.chat_message("assistant"): st.markdown(final_ai_reply.strip())
                        st.session_state.chat_messages.append({"role": "assistant", "content": final_ai_reply.strip()})
                        st.rerun()
                    except Exception as e:
                        st.error(f"System Error: {e}")

    with col_engine:
        st.subheader("⚙️ Action Center")
        
        # SYNC BUTTON (Sare tabs prompt data se bharega)
        if st.button("🔄 Sync Button (Extract Data)", use_container_width=True):
            if not anthropic_client: st.error("Anthropic API Key missing!")
            else:
                with st.spinner("Claude 3.5 Sonnet is building JSON data..."):
                    user_msgs = [msg['content'] for msg in st.session_state.chat_messages if msg["role"] == "user"]
                    
                    master_working_days = st.session_state.working_days
                    master_periods_per_day = st.session_state.periods_per_day
                    master_break_at = st.session_state.break_at
                    master_saturday_half_day = st.session_state.saturday_half_day
                    all_classes = []
                    all_rules = []
                    teacher_map = {}
                    
                    for idx, part in enumerate(user_msgs):
                        if part.strip().lower() == "done" or len(part) < 5:
                            continue 
                            
                        st.toast(f"Claude Extracting JSON from data part {idx+1} of {len(user_msgs)}...")
                        
                        extraction_prompt = (
                            "Carefully read this text chunk. Extract timing, classes, teachers (with Periods/Week logic), weekend half day info, AND ALL RULES.\n"
                            'Format EXACTLY like this JSON. Do not output anything else:\n'
                            '{\n'
                            '  "working_days": 6,\n'
                            '  "periods_per_day": 8,\n'
                            '  "break_at": 4,\n'
                            '  "saturday_half_day": false,\n'
                            '  "classes": ["1st A", "1st B"],\n'
                            '  "teachers": [{"Teacher Name": "Mr. Rohan Das", "Subject": "Maths", "Allowed Classes": "All", "Periods/Week (Per Class)": 6}],\n'
                            '  "fixed_rules": ["1st period on Monday is Class Teacher period", "Teacher cannot teach more than 3 continuous periods"]\n'
                            '}\n\n'
                            "Text Chunk:\n" + part
                        )
                        
                        try:
                            # MODEL 2: ANTHROPIC CLAUDE 3.5 SONNET (Perfect JSON Extraction)
                            response = anthropic_client.messages.create(
                                model="claude-3-5-sonnet-20241022",
                                max_tokens=2500,
                                temperature=0.1,
                                system="You are an expert JSON data extractor. Output ONLY raw valid JSON.",
                                messages=[
                                    {"role": "user", "content": extraction_prompt}
                                ]
                            )
                            
                            raw_output = response.content[0].text
                            clean_output = raw_output.strip()
                            bt = chr(96) * 3  
                            if clean_output.startswith(bt + "json"): clean_output = clean_output[7:]
                            elif clean_output.startswith(bt): clean_output = clean_output[3:]
                            if clean_output.endswith(bt): clean_output = clean_output[:-3]
                                    
                            part_data = json.loads(clean_output.strip())
                            
                            if part_data.get("working_days"): master_working_days = int(part_data["working_days"])
                            if part_data.get("periods_per_day"): master_periods_per_day = int(part_data["periods_per_day"])
                            if part_data.get("break_at"): master_break_at = int(part_data["break_at"])
                            
                            if "saturday_half_day" in part_data:
                                if str(part_data["saturday_half_day"]).lower() == "true":
                                    master_saturday_half_day = True
                                elif str(part_data["saturday_half_day"]).lower() == "false":
                                    master_saturday_half_day = False
                            
                            if part_data.get("classes"): all_classes.extend(part_data["classes"])
                            if part_data.get("fixed_rules"): all_rules.extend(part_data["fixed_rules"])
                            
                            if part_data.get("teachers"):
                                for t in part_data["teachers"]:
                                    name = t.get("Teacher Name", "Unknown").strip()
                                    sub = t.get("Subject", "").strip()
                                    cls = t.get("Allowed Classes", "").strip()
                                    p_week = t.get("Periods/Week (Per Class)", master_working_days) 
                                    
                                    if name in teacher_map:
                                        existing_subs = set([s.strip() for s in teacher_map[name]["Subject"].split(",")])
                                        new_subs = set([s.strip() for s in sub.split(",")])
                                        teacher_map[name]["Subject"] = ", ".join(existing_subs.union(new_subs))
                                        
                                        existing_cls = set([c.strip() for c in teacher_map[name]["Allowed Classes"].split(",")])
                                        new_cls = set([c.strip() for c in cls.split(",")])
                                        if "All" in existing_cls or "All" in new_cls:
                                            teacher_map[name]["Allowed Classes"] = "All"
                                        else:
                                            teacher_map[name]["Allowed Classes"] = ", ".join(existing_cls.union(new_cls))
                                            
                                        teacher_map[name]["Periods/Week (Per Class)"] = p_week
                                    else:
                                        t["Periods/Week (Per Class)"] = p_week
                                        teacher_map[name] = t
                            
                            time_module.sleep(1) 
                        except Exception as e:
                            continue
                    
                    st.session_state.working_days = int(max(1, min(7, master_working_days)))
                    st.session_state.periods_per_day = int(max(1, min(20, master_periods_per_day)))
                    st.session_state.break_at = int(max(1, min(15, master_break_at)))
                    st.session_state.saturday_half_day = master_saturday_half_day
                    
                    unique_classes = sorted(list(set(all_classes)))
                    if unique_classes:
                        st.session_state.classes_df = pd.DataFrame({"Class Name": unique_classes})
                        
                    if teacher_map:
                        st.session_state.teachers_df = pd.DataFrame(list(teacher_map.values()))
                        
                    if all_rules:
                        cleaned_rules = []
                        for r in all_rules:
                            rule_text = r.get("rule", r) if isinstance(r, dict) else r
                            cleaned_rules.append(str(rule_text))
                        st.session_state.rules_df = pd.DataFrame({"Rule": list(set(cleaned_rules))})
                        
                    st.success("✅ 2. Data Received and JSON successfully built! All Tabs updated. Now run the Engine.")
                    st.rerun()

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
                        if nums:
                            rule_max_consecutive = int(nums[0])
                
                days_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
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
                    
                    try:
                        p_per_class = int(t.get("Periods/Week (Per Class)", working_days))
                    except:
                        p_per_class = working_days
                        
                    if p_per_class > total_weekly_periods:
                         p_per_class = total_weekly_periods

                    if str(t_allowed_str).lower() == "all" or str(t_allowed_str) == "":
                        actual_classes = classes_list
                    else:
                        allowed_lower = [x.strip().lower() for x in str(t_allowed_str).split(",")]
                        actual_classes = [c for c in classes_list if c.lower() in allowed_lower]
                        
                    for c in actual_classes:
                        for sub in [s.strip() for s in t_sub_raw.split(",")]:
                            for _ in range(p_per_class):
                                class_requirements[c].append((t_name, sub))

                teacher_global_load = {}
                for c in classes_list:
                    for (t_name, sub) in class_requirements[c]:
                        teacher_global_load[t_name] = teacher_global_load.get(t_name, 0) + 1
                
                sanity_errors = []
                for (t_name, load) in teacher_global_load.items():
                    if t_name not in ["Library Master", "Self-Study"] and load > total_weekly_periods:
                        sanity_errors.append(f"Teacher '{t_name}' hafte ki {load} classes mili hain, par periods {total_weekly_periods} hain. Clash possible.")
                
                if sanity_errors:
                    st.error("🚨 WEEKLY DATA CONTRADICTIONS DETECTED:")
                    for err in sanity_errors: st.write(f"- {err}")

                for c in classes_list:
                    if len(class_requirements[c]) > total_weekly_periods:
                        random.shuffle(class_requirements[c]) 
                        class_requirements[c] = class_requirements[c][:total_weekly_periods]
                        
                    while len(class_requirements[c]) < total_weekly_periods:
                        class_requirements[c].append(("Self-Study", "Library"))

                st.info(f"🔄 Running Python Engine for {working_days} Days...")
                
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
                            if req[0] not in custom_busy[p_idx] or req[0] == "Self-Study":
                                t_name_check = req[0]
                                if t_name_check != "Self-Study":
                                    consecutive = 0
                                    for back_p in range(p_idx - 1, -1, -1):
                                        if "LUNCH" in period_labels[back_p]: break
                                        if t_name_check in custom_busy[back_p]: consecutive += 1
                                        else: break
                                    if consecutive >= rule_max_consecutive:
                                        continue 
                                
                                valid_reqs.append(req)
                    
                    random.shuffle(valid_reqs) 
                    
                    for req in valid_reqs:
                        t_name, sub = req
                        custom_timetable[c][p_idx] = f"{sub} ({t_name})"
                        custom_busy[p_idx].add(t_name)
                        custom_reqs[c].remove(req) 
                        
                        if solve_custom(next_p_idx, next_c_idx): return True
                        
                        custom_timetable[c][p_idx] = "Free"
                        if t_name != "Self-Study": custom_busy[p_idx].remove(t_name)
                        custom_reqs[c].append(req) 
                    return False

                custom_success = solve_custom(0, 0)
                
                if custom_success:
                    df = pd.DataFrame(custom_timetable)
                    df.insert(0, "Day / Period", period_labels)
                    st.success("✅ Engine Success: Timetable Generated with Rules!")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.warning("⚠️ Rules too strict. Custom Engine timed out. Falling back to Tier 2 (Google OR-Tools)...")
                    if not ORTOOLS_AVAILABLE:
                        st.error("❌ Fallback Failed: Google 'ortools' is not installed.")
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
                            for (t_name, sub) in ortools_reqs[c]:
                                if t_name != "Self-Study": all_teachers.add(t_name)

                        for p in valid_periods:
                            for teacher in all_teachers:
                                teacher_assignments_in_period = []
                                for c in classes_list:
                                    for (r_idx, req) in enumerate(ortools_reqs[c]):
                                        if req[0] == teacher:
                                            teacher_assignments_in_period.append(x[c][p][r_idx])
                                if len(teacher_assignments_in_period) > 1:
                                    model.AddAtMostOne(teacher_assignments_in_period)

                        if rule_max_consecutive < len(valid_periods):
                            day_wise_periods = {}
                            for p_idx_label, label in enumerate(period_labels):
                                if "LUNCH" not in label:
                                    day = label.split(" - ")[0]
                                    real_p = valid_periods[len([px for px in period_labels[:p_idx_label+1] if "LUNCH" not in px]) - 1]
                                    if day not in day_wise_periods:
                                        day_wise_periods[day] = []
                                    day_wise_periods[day].append(real_p)
                                    
                            for teacher in all_teachers:
                                for day, d_periods in day_wise_periods.items():
                                    for start_idx in range(len(d_periods) - rule_max_consecutive):
                                        window = d_periods[start_idx : start_idx + rule_max_consecutive + 1]
                                        teacher_vars_in_window = []
                                        for wp in window:
                                            for c in classes_list:
                                                for (r_idx, req) in enumerate(ortools_reqs[c]):
                                                    if req[0] == teacher:
                                                        teacher_vars_in_window.append(x[c][wp][r_idx])
                                        if teacher_vars_in_window:
                                            model.Add(sum(teacher_vars_in_window) <= rule_max_consecutive)

                        solver = cp_model.CpSolver()
                        solver.parameters.max_time_in_seconds = 30.0 
                        status = solver.Solve(model)

                        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                            for c in classes_list:
                                for p in valid_periods:
                                    for (r_idx, req) in enumerate(ortools_reqs[c]):
                                        if solver.Value(x[c][p][r_idx]) == 1:
                                            p_label_idx = -1
                                            for (idx, label) in enumerate(period_labels):
                                                if not "LUNCH" in label:
                                                    p_label_idx += 1
                                                    if p_label_idx == p - 1:
                                                        ortools_timetable[c][idx] = f"{req[1]} ({req[0]})"
                                                        break
                                            
                            df = pd.DataFrame(ortools_timetable)
                            df.insert(0, "Day / Period", period_labels)
                            st.success(f"✅ Tier 2 Success: Timetable generated via OR-Tools! (Status: {solver.StatusName(status)})")
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.error("❌ ABSOLUTE DEADLOCK! Engine failed.")
