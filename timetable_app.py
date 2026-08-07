import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
from groq import Groq
import json
import random
import sys

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
    st.info("Tip: If a teacher teaches multiple subjects, they will appear in multiple rows.")
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.header("Fixed Rules & Conditions")
    st.write("AI dwara nikale gaye fixed rules yahan dikhenge:")
    st.json(st.session_state.fixed_rules)

# ==========================================
# TAB 5: THE REAL PYTHON ENGINE (RULE ELIMINATION LOGIC)
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
                CRITICAL INSTRUCTIONS: 
                1. If a teacher teaches MULTIPLE subjects, create SEPARATE rows for them in the "teachers" list.
                2. Capture specific period durations in "durations".
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
    st.subheader("⚙️ 2. Run Engine (Constraint Elimination Method)")
    st.info("Engine ab 'Rule Elimination' method use karega. Pehle saari classes ki zarurat (requirements) list banayega, fir unhe ek-ek karke table mein set karega.")
    
    if st.button("🚀 Run Logical Engine & Generate", type="primary"):
        with st.spinner("Python Engine is solving using Rule Elimination Logic..."):
            sys.setrecursionlimit(5000)
            
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
            
            timetable = {c: ["Free"] * len(period_labels) for c in classes_list} 
            for c in classes_list:
                timetable[c][break_at] = "LUNCH / BREAK"
                
            busy_teachers_per_period = {i: set() for i in range(len(period_labels))}
            
            # --- STEP 1: GATHER REQUIREMENTS (THE HUMAN LOGIC) ---
            # Har class ko kya-kya padhna hai, uski ek list banayenge
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

            # --- STEP 2: APPLY FIXED RULES & REMOVE FROM REQUIREMENTS ---
            for rule in fixed_rules:
                p = rule.get("period", 1)
                c = rule.get("class", "")
                sub = rule.get("subject", "")
                teacher = rule.get("teacher", "")
                row_idx = p - 1 if p <= break_at else p
                if c in classes_list and row_idx < len(period_labels):
                    timetable[c][row_idx] = f"{sub} ({teacher})"
                    busy_teachers_per_period[row_idx].add(teacher)
                    
                    # Remove this specific requirement so engine doesn't assign it again
                    req_tuple = (teacher, sub)
                    if req_tuple in class_requirements[c]:
                        class_requirements[c].remove(req_tuple)

            # --- STEP 3: CONSTRAINT ELIMINATION BACKTRACKING ---
            def solve_logical(p_idx, c_idx):
                if p_idx >= len(period_labels):
                    return True # Completed!
                
                if "BREAK" in period_labels[p_idx]:
                    return solve_logical(p_idx + 1, 0)
                
                c = classes_list[c_idx]
                
                next_c_idx = c_idx + 1
                next_p_idx = p_idx
                if next_c_idx >= len(classes_list):
                    next_c_idx = 0
                    next_p_idx += 1
                
                # If slot already filled by a fixed rule, skip
                if timetable[c][p_idx] != "Free":
                    return solve_logical(next_p_idx, next_c_idx)
                
                # If class has no more requirements, leave it free and continue
                if len(class_requirements[c]) == 0:
                    return solve_logical(next_p_idx, next_c_idx)
                
                # Find which requirements can be fulfilled in this slot
                valid_reqs = []
                seen_reqs = set()
                for req in class_requirements[c]:
                    if req not in seen_reqs: # Don't process duplicates
                        seen_reqs.add(req)
                        t_name, sub = req
                        if t_name not in busy_teachers_per_period[p_idx]:
                            valid_reqs.append(req)
                
                # Sort valid reqs to prioritize teachers who have fewer valid slots (Heuristic)
                random.shuffle(valid_reqs) # Shuffle for variation
                
                for req in valid_reqs:
                    t_name, sub = req
                    
                    # PLACE IN TIMETABLE
                    timetable[c][p_idx] = f"{sub} ({t_name})"
                    busy_teachers_per_period[p_idx].add(t_name)
                    class_requirements[c].remove(req) # ELIMINATE FROM REQUIREMENTS
                    
                    if solve_logical(next_p_idx, next_c_idx):
                        return True
                    
                    # UNDO (Backtrack)
                    timetable[c][p_idx] = "Free"
                    busy_teachers_per_period[p_idx].remove(t_name)
                    class_requirements[c].append(req) # PUT BACK IN REQUIREMENTS
                
                return False

            start_time = time_module.time()
            success = solve_logical(0, 0)
            
            df = pd.DataFrame(timetable)
            df.insert(0, "Time / Period", period_labels)
            
            if not success:
                st.error("⚠️ LOGICAL DEADLOCK! Engine ne saari requirements list padhi, par time table fit nahi ho pa raha hai.")
                st.info("💡 Karan: Kisi ek period mein 2 classes ko same teacher chahiye, ya kisi class mein periods se zyada subjects hain. Kripya Tab 3 check karein.")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.success("✅ Perfect Timetable Generated using Rule Elimination! Engine ne pehle lists banayi, fir tick mark karke table bhara.")
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
