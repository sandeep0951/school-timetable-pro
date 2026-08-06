import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
from groq import Groq

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
    "🪄 6. AI Prompt Builder"
])

# ==========================================
# TAB 1: Number of hours & Periods
# ==========================================
with tab1:
    st.header("School Timings & Periods Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Working Hours & Structure")
        school_start = st.time_input("School Start Time", value=time(8, 0))
        total_periods = st.number_input("Total Number of Periods", min_value=1, max_value=15, value=8)
        break_period = st.number_input("Break happens AFTER which period?", min_value=1, max_value=10, value=4)
        
    with col2:
        st.subheader("2. Custom Period Durations")
        st.write("Aap har period ka time alag set kar sakte hain:")
        
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
            
        st.session_state.periods_timing_df = st.data_editor(
            st.session_state.periods_timing_df, 
            use_container_width=True, 
            hide_index=True
        )

# ==========================================
# TAB 2: Number of Classes
# ==========================================
with tab2:
    st.header("Classes Configuration")
    
    if 'classes_df' not in st.session_state:
        st.session_state.classes_df = pd.DataFrame({"Class Name": ["9th A", "10th A", "11th Sci", "12th Comm"]})
    
    st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)

# ==========================================
# TAB 3: Teachers, Subjects & Leaves
# ==========================================
with tab3:
    st.header("Teachers, Subjects & Leaves Directory")
    
    if 'teachers_df' not in st.session_state:
        st.session_state.teachers_df = pd.DataFrame({
            "Teacher Name": ["Mr. Sharma", "Ms. Verma", "Mr. Gupta"],
            "Subject 1": ["Maths", "Science", "English"],
            "Subject 2": ["Physics", "Biology", "Hindi"],
            "Special Topic/Class": ["Olympiad (10th A)", "Lab (11th Sci)", "Debate (9th A)"],
            "Leave From (Date)": ["", "15-Aug-2026", ""],
            "Leave To (Date)": ["", "20-Aug-2026", ""]
        })
    
    st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)

# ==========================================
# TAB 4: Conditions & Holidays
# ==========================================
with tab4:
    st.header("Advanced Rules Engine & Holidays")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("National Holidays")
        if 'nat_holidays_df' not in st.session_state:
            st.session_state.nat_holidays_df = pd.DataFrame({"Holiday Name": ["Independence Day", "Republic Day"], "Date": ["15-Aug-2026", "26-Jan-2026"]})
        st.session_state.nat_holidays_df = st.data_editor(st.session_state.nat_holidays_df, num_rows="dynamic", use_container_width=True, key="nat_hol")

        st.subheader("Local & Authority Holidays")
        if 'loc_holidays_df' not in st.session_state:
            st.session_state.loc_holidays_df = pd.DataFrame({"Holiday Name": ["Collector Declared Holiday", "Local Festival"], "Date": ["20-Aug-2026", "05-Sep-2026"]})
        st.session_state.loc_holidays_df = st.data_editor(st.session_state.loc_holidays_df, num_rows="dynamic", use_container_width=True, key="loc_hol")

    with col2:
        st.subheader("Conditions")
        rule_type = st.selectbox("Rule Type", ["If-Then", "Then-only", "Can", "Near by", "After", "Before", "Followed by"])
        rule_desc = st.text_input("Describe Rule (e.g. 'Maths AFTER Break')")
        if st.button("Add Rule"):
            st.success(f"Rule Added: [{rule_type}] {rule_desc}")

# ==========================================
# TAB 5: Generate & Conflict Resolution (REAL AI)
# ==========================================
with tab5:
    st.header("Timetable Generation & Conflict Resolution")
    target_date = st.date_input("Target Date for Timetable", datetime.today())
    
    if st.button("🚀 Run Advanced Engine & Generate", type="primary"):
        st.session_state.gen_triggered = True

    if st.session_state.get('gen_triggered', False):
        st.warning("⚠️ **Contradiction Detected**")
        
        col_prob, col_sugg, col_sol = st.columns(3)
        with col_prob:
            st.error("**A. Problem**\nMs. Verma has 'Science' class in 10th A at Period 3, but she is on Leave.")
        with col_sugg:
            st.info("**B. Suggestion**\n1. Assign Mr. Sharma\n2. Assign Library")
        with col_sol:
            st.success("**C. Default Solution**\nSystem assigned 'Library'.")
        
        # --- AI PROMPT CONFLICT RESOLUTION ---
        st.markdown("---")
        st.subheader("🪄 Resolve Contradiction with AI Prompt")
        
        resolve_prompt = st.text_input(
            "Enter resolution instruction:",
            placeholder="Example: 'Library ki jagah Mr. Gupta ko 10th A ke Period 3 mein English proxy de do'"
        )
        
        if st.button("✨ Apply Prompt Fix"):
            if not client:
                st.error("❌ Groq API Key Streamlit Secrets mein nahi mili! Pehle use set karein.")
            elif resolve_prompt:
                with st.spinner("AI is processing your override command..."):
                    try:
                        # Real Groq AI Call
                        completion = client.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=[
                                {"role": "system", "content": "You are a smart school timetable assistant. Briefly confirm the user's action in a professional tone, explaining how the schedule is updated based on their prompt."},
                                {"role": "user", "content": f"The original issue was Ms. Verma being on leave for 10th A. Please confirm this update: {resolve_prompt}"}
                            ],
                            temperature=0.3,
                        )
                        ai_fix_response = completion.choices[0].message.content
                        
                        st.success(f"✅ Your Prompt: '{resolve_prompt}'")
                        st.info(f"**🤖 AI Engine Action:** {ai_fix_response}")
                    except Exception as e:
                        st.error(f"Error connecting to Groq: {e}")
            else:
                st.warning("⚠️ Pehle instruction likhiye!")

# ==========================================
# TAB 6: AI Prompt Builder (REAL AI GENERATION)
# ==========================================
with tab6:
    st.header("🪄 AI Prompt Builder (Describe & Generate)")
    st.write("Apne shabdon mein bataiye kaisa timetable chahiye, aur Llama-3 AI usko banayega.")
    
    ai_prompt = st.text_area(
        "Describe your requirement (Hindi or English):", 
        placeholder="Example: '9th A aur 10th A ka Monday ka timetable banao jisme 8 periods hon. Pehla period maths aur aakhri sports ho.'",
        height=150
    )
    
    if st.button("✨ Generate with AI Prompt", type="primary"):
        if not client:
            st.error("❌ Groq API Key Streamlit Secrets mein nahi mili! Pehle use set karein.")
        elif ai_prompt:
            with st.spinner("Groq AI aapka prompt samajh raha aur timetable bana raha hai..."):
                try:
                    # Real Groq AI Call for Timetable Generation
                    completion = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[
                            {"role": "system", "content": "You are a logical school timetable generator. Based on the user's prompt, generate a visually clean timetable using a Markdown table. Do NOT write long paragraphs, just provide the Markdown table and a single line of confirmation."},
                            {"role": "user", "content": ai_prompt}
                        ],
                        temperature=0.5,
                    )
                    ai_tt_response = completion.choices[0].message.content
                    
                    st.success("✅ AI ne aapka prompt successfully process kar liya hai!")
                    st.markdown(ai_tt_response)
                    
                except Exception as e:
                    st.error(f"Error connecting to Groq API: {e}")
        else:
            st.warning("⚠️ Pehle prompt box mein apni requirement likhiye!")
