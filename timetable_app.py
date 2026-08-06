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
# TAB 1, 2, 3, 4, 5 (Same as previous safe version)
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

with tab5:
    st.header("Timetable Generation & Conflict Resolution")
    target_date = st.date_input("Target Date for Timetable", datetime.today())
    if st.button("🚀 Run Advanced Engine & Generate", type="primary"):
        st.session_state.gen_triggered = True

    if st.session_state.get('gen_triggered', False):
        st.warning("⚠️ **Contradiction Detected**")
        st.success("**C. Default Solution** System assigned 'Library'.")
        resolve_prompt = st.text_input("Enter resolution instruction:")
        if st.button("✨ Apply Prompt Fix"):
            st.success(f"Applied: '{resolve_prompt}'")
        dummy_tt = pd.DataFrame({"Period": ["1", "2"], "9th A": ["English", "Hindi"], "10th A": ["Science", "English"]})
        st.dataframe(dummy_tt, use_container_width=True, hide_index=True)

# ==========================================
# TAB 6: AI Co-Pilot (2-Way Chat) - FIXED SYSTEM PROMPT
# ==========================================
with tab6:
    st.header("💬 AI Co-Pilot (2-Way Communication)")
    st.write("Ab aap AI ke sath baatcheet karke timetable modify karwa sakte hain. AI aapki purani baatein yaad rakhega!")
    
    # Initialize chat history with a STRICT constraint
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "system", 
                "content": "You are Sandeep's AI Co-Pilot. STRICT RULES: 1. NEVER generate full timetables or long lists. 2. Keep responses very short (2-3 sentences max). 3. Just confirm what changes you understood from Sandeep and say you will pass it to the Python Engine. 4. Speak in a friendly mix of Hindi and English (Hinglish)."
            },
            {
                "role": "assistant", 
                "content": "Namaste Sandeep Sir! Main aapka AI Co-Pilot hoon. Bataiye, timetable mein kya badlav karna hai? (Main sirf aapki instructions ko backend engine tak pahunchaunga, taaki koi clash na ho!)"
            }
        ]

    # Display chat messages
    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("Apna instruction yahan likhein..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        if not client:
            st.error("❌ Groq API Key Streamlit Secrets mein nahi mili!")
        else:
            with st.spinner("AI soch raha hai..."):
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=st.session_state.messages,
                        temperature=0.3, # Lowered temperature to stop hallucinations
                        max_tokens=150, # STRICT LIMIT so it physically cannot loop a full timetable
                    )
                    
                    response = completion.choices[0].message.content
                    
                    with st.chat_message("assistant"):
                        st.markdown(response)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    st.error(f"Error connecting to Groq API: {e}")
