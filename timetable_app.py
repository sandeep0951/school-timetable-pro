import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
from groq import Groq
import json

# App Configuration
st.set_page_config(page_title="Advanced Timetable Pro", layout="wide")

# Initialize Groq Client using Streamlit Secrets
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
# TAB 1, 2, 3, 4 (Configuration)
# ==========================================
with tab1:
    st.header("School Timings & Periods Configuration")
    col1, col2 = st.columns(2)
    with col1:
        school_start = st.time_input("School Start Time", value=time(8, 0))
        total_periods = st.number_input("Total Number of Periods", min_value=1, max_value=15, value=8)
        break_period = st.number_input("Break happens AFTER which period?", min_value=1, max_value=10, value=4)
    with col2:
        if 'last_total' not in st.session_state or st.session_state.last_total != total_periods or st.session_state.last_break != break_period:
            slots = []
            for i in range(1, total_periods + 1):
                duration = 50 if i == 1 else 45
                slots.append({"Slot": f"Period {i}", "Duration (Mins)": duration})
                if i == break_period:
                    slots.append({"Slot": "LUNCH BREAK", "Duration (Mins)": 30})
            st.session_state.periods_timing_df = pd.DataFrame(slots)
            st.session_state.last_total = total_periods
            st.session_state.last_break = break_period
        st.session_state.periods_timing_df = st.data_editor(st.session_state.periods_timing_df, use_container_width=True, hide_index=True)

with tab2:
    st.header("Classes Configuration")
    if 'classes_df' not in st.session_state:
        st.session_state.classes_df = pd.DataFrame({"Class Name": ["9th A", "10th A", "11th Sci", "12th Comm"]})
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

with tab3:
    st.header("Teachers, Subjects & Leaves Directory")
    if 'teachers_df' not in st.session_state:
        st.session_state.teachers_df = pd.DataFrame({
            "Teacher Name": ["Mr. Sharma", "Ms. Verma", "Mr. Gupta", "Sandip Sir", "Nikum Sir", "Banshi Sir"],
            "Subject 1": ["Maths", "Science", "English", "Maths", "Maths", "Hindi"],
            "Subject 2": ["Physics", "Biology", "Hindi", "-", "-", "Social"],
            "Special Topic/Class": ["Olympiad (10th A)", "Lab (11th Sci)", "Debate (9th A)", "-", "-", "-"],
            "Leave From (Date)": ["", "15-Aug-2026", "", "", "", ""],
            "Leave To (Date)": ["", "20-Aug-2026", "", "", "", ""]
        })
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

with tab4:
    st.header("Advanced Rules Engine & Holidays")
    col1, col2 = st.columns(2)
    with col1:
        if 'nat_holidays_df' not in st.session_state:
            st.session_state.nat_holidays_df = pd.DataFrame({"Holiday Name": ["Independence Day"], "Date": ["15-Aug-2026"]})
        st.session_state.nat_holidays_df = st.data_editor(st.session_state.nat_holidays_df, num_rows="dynamic", use_container_width=True, key="nat_hol")
    with col2:
        rule_type = st.selectbox("Rule Type", ["If-Then", "Then-only", "Can", "After", "Before"])
        rule_desc = st.text_input("Describe Rule")
        if st.button("Add Rule"):
            st.success(f"Rule Added: [{rule_type}] {rule_desc}")

# ==========================================
# TAB 5: Python Engine & AI Data Bridge
# ==========================================
with tab5:
    st.header("Timetable Generation & Conflict Resolution")
    target_date = st.date_input("Target Date for Timetable", datetime.today())
    
    st.markdown("---")
    st.subheader("🧠 1. Fetch AI Rules (Bridge from Tab 6)")
    st.write("Tab 6 mein AI se hui baatcheet ko yahan JSON rules mein convert karein:")
    
    if st.button("🔄 Extract Rules from AI Chat"):
        if not client:
            st.error("Groq API Key missing!")
        elif "chat_messages" not in st.session_state or len(st.session_state.chat_messages) <= 2:
            st.warning("⚠️ Pehle Tab 6 mein AI se kuch rules discuss karein!")
        else:
            with st.spinner("Translating Chat History into Python Constraints..."):
                chat_history = str(st.session_state.chat_messages)
                extraction_prompt = f"Extract all timetable rules and constraints from this chat history into a strict JSON format. ONLY output JSON. Format: {{'rules': ['rule 1', 'rule 2'], 'teachers_mentioned': []}}. Chat History: {chat_history}"
                
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
                    
    if "final_ai_rules" in st.session_state:
        st.info("💡 Engine is ready to apply these AI constraints.")

    st.markdown("---")
    st.subheader("⚙️ 2. Run Python Logic Engine")
    if st.button("🚀 Run Advanced Engine & Generate", type="primary"):
        st.session_state.gen_triggered = True

    if st.session_state.get('gen_triggered', False):
        st.warning("⚠️ **Contradiction Detected (Dummy Logic)**")
        st.success("**C. Default Solution** System assigned 'Library'.")
        
        # Simulated Output
        dummy_tt = pd.DataFrame({
            "Period": ["1", "2", "3", "Break"], 
            "9th A": ["English", "Hindi", "Science", "LUNCH"], 
            "10th A": ["Science", "English", "Library (Proxy)", "LUNCH"]
        })
        st.dataframe(dummy_tt, use_container_width=True, hide_index=True)

# ==========================================
# TAB 6: AI Co-Pilot (70B MODEL CHAT ONLY)
# ==========================================
with tab6:
    st.header("💬 AI Co-Pilot (Data Collector)")
    st.write("Yahan AI se normal language mein baat karein. Yeh sirf data collect karega. Asli table Tab 5 mein banega.")
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "system", 
                "content": '''You are Sandeep's Data Extractor Assistant. 
                CRITICAL RULES:
                1. YOU MUST NEVER GENERATE A TIMETABLE. 
                2. NEVER write time slots or class schedules.
                3. Your ONLY job is to listen to the user's constraints, extract the rules, and say: "Maine ye rules note kar liye hain. Kripya Tab 5 mein jaakar 'Extract Rules' par click karein." 
                4. Always speak in polite Hinglish.'''
            },
            {
                "role": "assistant", 
                "content": "Namaste Sandeep Sir! Main aapka AI Assistant hoon. Mujhe apne naye rules bataiye, main unhe note kar lunga. (Timetable Tab 5 mein generate hoga)."
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
            st.error("❌ Groq API Key Streamlit Secrets mein nahi mili!")
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
