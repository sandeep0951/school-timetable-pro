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

# --- TAB LAYOUT ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🕒 1. Timings & Periods", 
    "🏫 2. Classes & Subjects", 
    "👨‍🏫 3. Teachers & Leaves", 
    "⚙️ 4. Rules & Holidays", 
    "🚀 5. Generate & Resolve",
    "💬 6. AI Co-Pilot (2-Way Chat)"
])

# ==========================================
# TABS 1-4 (Same basic config)
# ==========================================
with tab1:
    st.header("School Timings & Periods Configuration")
    total_periods = st.number_input("Total Number of Periods", min_value=1, max_value=15, value=7)
    break_period = st.number_input("Break happens AFTER which period?", min_value=1, max_value=10, value=3)

with tab2:
    st.header("Classes Configuration")
    st.info("Configured via AI Rules dynamically.")

with tab3:
    st.header("Teachers Directory")
    st.info("Configured via AI Rules dynamically.")

with tab4:
    st.header("Holidays")
    st.info("No holidays for this week.")

# ==========================================
# TAB 5: THE REAL PYTHON ENGINE (WITH AUTO-FILL)
# ==========================================
with tab5:
    st.header("Timetable Generation & Conflict Resolution")
    
    st.subheader("🧠 1. Fetch AI Rules (Bridge from Tab 6)")
    if st.button("🔄 Extract Rules from AI Chat"):
        if not client:
            st.error("Groq API Key missing!")
        elif "chat_messages" not in st.session_state or len(st.session_state.chat_messages) <= 2:
            st.warning("⚠️ Pehle Tab 6 mein AI se kuch rules discuss karein!")
        else:
            with st.spinner("Translating Chat History into Python Constraints..."):
                chat_history = str(st.session_state.chat_messages)
                extraction_prompt = '''Extract ALL timetable rules, teachers, and classes from the chat history into a strict JSON format. 
                ONLY output JSON. 
                Format MUST be exactly like this structure:
                {
                    "total_periods": 7,
                    "break_after": 3,
                    "classes": ["6th A", "6th B", "7th", "8th", "9th", "10th"],
                    "fixed_rules": [
                        {"period": 1, "class": "10th", "subject": "Maths", "teacher": "Nikum"}
                    ],
                    "teacher_mappings": [
                        {"teacher": "Balram", "subject": "Sanskrit", "allowed_classes": ["6th A", "6th B", "7th", "8th", "9th"]},
                        {"teacher": "Rudra", "subject": "Science", "allowed_classes": ["6th A", "6th B", "7th", "8th"]}
                    ]
                }
                Make sure to include ALL teachers and their allowed classes in 'teacher_mappings'. Chat History: ''' + chat_history
                
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": extraction_prompt}],
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    extracted_data = json.loads(completion.choices[0].message.content)
                    st.session_state.final_ai_rules = extracted_data
                    st.success("✅ Rules successfully bridged to Python Engine!")
                    st.json(extracted_data)
                except Exception as e:
                    st.error(f"Failed to extract rules: {e}")
                    
    st.markdown("---")
    st.subheader("⚙️ 2. Run Python Logic Engine (Auto-Fill & No Clash)")
    
    if st.button("🚀 Run Advanced Engine & Generate", type="primary"):
        if "final_ai_rules" not in st.session_state:
            st.error("⚠️ Pehle upar 'Extract Rules' button dabayein taaki engine ko data mil sake!")
        else:
            with st.spinner("Python Engine is calculating clashes and Auto-Filling grid..."):
                time_module.sleep(1.5) # Processing simulation
                
                rules = st.session_state.final_ai_rules
                classes = rules.get("classes", ["6th A", "6th B", "7th", "8th", "9th", "10th"])
                periods_count = rules.get("total_periods", 7)
                break_at = rules.get("break_after", 3)
                fixed_rules = rules.get("fixed_rules", [])
                teacher_mappings = rules.get("teacher_mappings", [])
                
                # 1. Create empty grid
                timetable = {c: ["Free"] * (periods_count + 1) for c in classes} # +1 for break
                period_labels = []
                
                p_idx = 0
                for i in range(1, periods_count + 2):
                    if i == break_at + 1:
                        period_labels.append("BREAK (15 min)")
                        for c in classes:
                            timetable[c][i-1] = "LUNCH / BREAK"
                    else:
                        p_idx += 1
                        period_labels.append(f"Period {p_idx}")
                
                # 2. Apply Fixed Rules from JSON
                busy_teachers_per_period = {i: set() for i in range(len(period_labels))}
                
                for rule in fixed_rules:
                    p = rule.get("period", 1)
                    c = rule.get("class", "")
                    sub = rule.get("subject", "")
                    teacher = rule.get("teacher", "")
                    
                    row_idx = p - 1 if p <= break_at else p
                    
                    if c in classes and row_idx < len(period_labels):
                        timetable[c][row_idx] = f"{sub} ({teacher})"
                        busy_teachers_per_period[row_idx].add(teacher)

                # 3. AUTO-FILL ALGORITHM (Greedy filling without clashes)
                for row_idx in range(len(period_labels)):
                    if "BREAK" in period_labels[row_idx]:
                        continue
                    
                    for c in classes:
                        if timetable[c][row_idx] == "Free":
                            # Find all teachers who are allowed to teach this class AND are not busy this period
                            available_options = []
                            for mapping in teacher_mappings:
                                t_name = mapping.get("teacher")
                                t_sub = mapping.get("subject")
                                allowed_c = mapping.get("allowed_classes", [])
                                
                                if c in allowed_c and t_name not in busy_teachers_per_period[row_idx]:
                                    available_options.append((t_name, t_sub))
                            
                            if available_options:
                                # Pick a random available teacher for variation
                                chosen_teacher, chosen_sub = random.choice(available_options)
                                timetable[c][row_idx] = f"{chosen_sub} ({chosen_teacher})"
                                busy_teachers_per_period[row_idx].add(chosen_teacher)
                            else:
                                timetable[c][row_idx] = "Free (No Teacher)"

                # Build DataFrame
                df = pd.DataFrame(timetable)
                df.insert(0, "Time / Period", period_labels)
                
                st.success("✅ Python Engine successfully Auto-Filled the Grid with 0 Clashes!")
                st.dataframe(df, use_container_width=True, hide_index=True)

# ==========================================
# TAB 6: AI Co-Pilot (70B MODEL CHAT ONLY)
# ==========================================
with tab6:
    st.header("💬 AI Co-Pilot (Data Collector)")
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "system", 
                "content": '''You are Sandeep's Data Extractor Assistant. 
                CRITICAL RULES:
                1. NEVER GENERATE A TIMETABLE IN CHAT.
                2. Your ONLY job is to listen, understand constraints, and tell the user: "Maine rules note kar liye hain. Tab 5 mein jaakar Extract dabayein." 
                3. Speak in polite Hinglish.'''
            },
            {
                "role": "assistant", 
                "content": "Namaste Sandeep Sir! Main aapka AI Assistant hoon. Mujhe apne rules bataiye, main unhe JSON format ke liye note kar lunga. Timetable Tab 5 mein banega."
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
