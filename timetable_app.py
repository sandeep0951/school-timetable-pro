import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
from groq import Groq
import json
import random

# App Configuration
st.set_page_config(page_title="Advanced Timetable Pro", layout="wide")

# Initialize Groq Client
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_api_key)
except:
    client = None

# App Header
st.title("🏫 Advanced Timetable Pro (Custom Version)")
st.markdown("Developed by Sandeep | Fully Customizable Engine")

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
    "🚀 5. Generate & Resolve",
    "💬 6. AI Co-Pilot"
])

# ==========================================
# TABS 1-4 (SYNCED WITH AI UI)
# ==========================================
with tab1:
    st.header("School Timings & Periods Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.num_periods = st.number_input("Total Number of Periods", min_value=1, max_value=15, value=st.session_state.num_periods)
        st.session_state.break_at = st.number_input("Break happens AFTER which period?", min_value=1, max_value=10, value=st.session_state.break_at)
    
    with col2:
        st.write("Custom Period Durations (AI updates reflect here):")
        st.session_state.periods_timing_df = st.data_editor(st.session_state.periods_timing_df, use_container_width=True, hide_index=True)

with tab2:
    st.header("Classes Configuration")
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.header("Teachers & Subject Mapping")
    st.info("Tip: If a teacher teaches multiple subjects, they will appear in multiple rows. (e.g., Dipendra for English and Maths).")
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.header("Fixed Rules & Conditions")
    st.write("AI dwara nikale gaye fixed rules yahan dikhenge:")
    st.json(st.session_state.fixed_rules)

# ==========================================
# TAB 5: THE REAL PYTHON ENGINE (SMART AUTO-FILL WITH BACKTRACKING/RETRY)
# ==========================================
with tab5:
    st.header("Timetable Generation & Conflict Resolution")
    
    st.subheader("🧠 1. Fetch AI Rules (Bridge from Tab 6)")
    
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
    st.subheader("⚙️ 2. Run Engine (With 500x Auto-Correction Retry)")
    
    if st.button("🚀 Run Engine & Generate", type="primary"):
        with st.spinner("Python Engine is solving constraints using Monte Carlo method (trying hundreds of combinations)..."):
            
            classes_list = st.session_state.classes_df["Class Name"].dropna().tolist()
            teachers_list = st.session_state.teachers_df.to_dict('records')
            periods_count = st.session_state.num_periods
            break_at = st.session_state.break_at
            fixed_rules = st.session_state.fixed_rules
            
            period_labels = []
            p_idx = 0
            for i in range(1, periods_count + 2):
                if i == break_at + 1:
                    period_labels.append("BREAK")
                else:
                    p_idx += 1
                    period_labels.append(f"Period {p_idx}")
            
            max_attempts = 500  # Try 500 different random combinations
            best_timetable = None
            best_conflicts = ["Dummy"] * 1000 
            
            for attempt in range(max_attempts):
                timetable = {c: ["Free"] * len(period_labels) for c in classes_list} 
                for c in classes_list:
                    timetable[c][break_at] = "LUNCH / BREAK"
                    
                busy_teachers_per_period = {i: set() for i in range(len(period_labels))}
                subject_counts_per_class = {c: {} for c in classes_list}
                teacher_counts_per_class = {c: set() for c in classes_list} 
                
                conflicts = []
                
                # Apply Fixed Rules first
                for rule in fixed_rules:
                    p = rule.get("period", 1)
                    c = rule.get("class", "")
                    sub = rule.get("subject", "")
                    teacher = rule.get("teacher", "")
                    row_idx = p - 1 if p <= break_at else p
                    if c in classes_list and row_idx < len(period_labels):
                        if teacher not in busy_teachers_per_period[row_idx]:
                            timetable[c][row_idx] = f"{sub} ({teacher})"
                            busy_teachers_per_period[row_idx].add(teacher)
                            subject_counts_per_class[c][sub] = subject_counts_per_class[c].get(sub, 0) + 1
                            teacher_counts_per_class[c].add(teacher)

                # Shuffle classes to avoid deterministic deadlocks
                shuffled_classes = classes_list.copy()
                
                # AUTO-FILL
                for row_idx in range(len(period_labels)):
                    if "BREAK" in period_labels[row_idx]:
                        continue
                    
                    random.shuffle(shuffled_classes) # Randomize class filling order
                    
                    for c in shuffled_classes:
                        if timetable[c][row_idx] == "Free":
                            available_options = []
                            for t in teachers_list:
                                t_name = t.get("Teacher Name", "")
                                t_sub = t.get("Subject", "")
                                t_allowed_str = str(t.get("Allowed Classes", "")).strip()
                                
                                if t_allowed_str.lower() == "all" or t_allowed_str == "":
                                    t_allowed = classes_list
                                else:
                                    t_allowed = [x.strip() for x in t_allowed_str.split(",")]
                                    
                                if (c in t_allowed and 
                                    t_name not in busy_teachers_per_period[row_idx] and 
                                    subject_counts_per_class[c].get(t_sub, 0) < 1 and
                                    t_name not in teacher_counts_per_class[c]):
                                    
                                    available_options.append((t_name, t_sub))
                            
                            if available_options:
                                chosen_teacher, chosen_sub = random.choice(available_options)
                                timetable[c][row_idx] = f"{chosen_sub} ({chosen_teacher})"
                                busy_teachers_per_period[row_idx].add(chosen_teacher)
                                subject_counts_per_class[c][chosen_sub] = subject_counts_per_class[c].get(chosen_sub, 0) + 1
                                teacher_counts_per_class[c].add(chosen_teacher)
                            else:
                                timetable[c][row_idx] = "❌ Clash"
                                conflicts.append(f"Class '{c}', Period {period_labels[row_idx]}: Deadlock occurred.")

                # If perfect table found, break loop
                if not conflicts:
                    best_timetable = timetable
                    best_conflicts = []
                    break
                
                # Otherwise, keep the one with the least conflicts
                if len(conflicts) < len(best_conflicts):
                    best_timetable = timetable
                    best_conflicts = conflicts

            # Show Results
            df = pd.DataFrame(best_timetable)
            df.insert(0, "Time / Period", period_labels)
            
            if best_conflicts:
                st.warning(f"⚠️ Engine tried {max_attempts} combinations but couldn't resolve {len(best_conflicts)} clashes perfectly. The rules might be mathematically impossible.")
                st.info("💡 Hint: Add more teachers or loosen the 'Allowed Classes' restrictions in Tab 3.")
            else:
                st.success(f"✅ Timetable Generated Successfully with 0 Clashes! (Solved on attempt {attempt + 1})")
            
            st.dataframe(df, use_container_width=True, hide_index=True)

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
