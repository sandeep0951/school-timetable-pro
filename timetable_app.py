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
            "Teacher Name": ["Mr. Sharma", "Ms. Verma", "Mr. Gupta", "Sandip Sir", "Nikum Sir", "Banshi Sir"],
            "Subject 1": ["Maths", "Science", "English", "Maths", "Maths", "Hindi"],
            "Subject 2": ["Physics", "Biology", "Hindi", "-", "-", "Social"],
            "Special Topic/Class": ["Olympiad (10th A)", "Lab (11th Sci)", "Debate (9th A)", "-", "-", "-"],
            "Leave From (Date)": ["", "15-Aug-2026", "", "", "", ""],
            "Leave To (Date)": ["", "20-Aug-2026", "", "", "", ""]
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
# TAB 5: Generate & Conflict Resolution (Python Logic Engine)
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

        st.markdown("---")
        st.subheader(f"Generated Timetable for {target_date.strftime('%d-%b-%Y')} (Python Engine)")
        
        total_rows_to_show = total_periods + 1
        dummy_tt = pd.DataFrame({
            "Period": ["1", "2", "3", "Break", "4", "5", "6", "7", "8"],
            "Time": ["08:00 - 08:50", "08:50 - 09:35", "09:35 - 10:20", "10:20 - 10:50", "10:50 - 11:35", "11:35 - 12:20", "12:20 - 13:05", "13:05 - 13:50", "13:50 - 14:35"],
            "9th A": ["English", "Hindi", "Science", "LUNCH", "Maths", "Sports", "Library", "Art", "Free"],
            "10th A": ["Science", "English", "Library (Proxy)", "LUNCH", "Hindi", "Maths", "Sports", "History", "Free"]
        })
        display_tt = dummy_tt.head(total_rows_to_show) if total_rows_to_show <= len(dummy_tt) else dummy_tt
        st.dataframe(display_tt, use_container_width=True, hide_index=True)

# ==========================================
# TAB 6: AI Co-Pilot (2-Way Chat)
# ==========================================
with tab6:
    st.header("💬 AI Co-Pilot (2-Way Communication)")
    st.write("Ab aap AI ke sath baatcheet karke timetable modify karwa sakte hain. AI aapki purani baatein yaad rakhega!")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "You are a helpful school timetable assistant for Sandeep. IMPORTANT RULE: A teacher CANNOT be in two classes at the same time. Never violate this. Help him refine the timetable step-by-step. Speak in a friendly mix of Hindi and English (Hinglish)."},
            {"role": "assistant", "content": "Namaste Sandeep Sir! Main aapka AI Co-Pilot hoon. Bataiye, timetable mein kya set karna hai ya kaunsa badlav karna hai?"}
        ]

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        if message["role"] != "system": # Hide the system prompt from the UI
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("Apna instruction yahan likhein..."):
        # Display user message in chat message container
        st.chat_message("user").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        if not client:
            st.error("❌ Groq API Key Streamlit Secrets mein nahi mili!")
        else:
            with st.spinner("AI soch raha hai..."):
                try:
                    # Send entire history to Groq for context
                    completion = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=st.session_state.messages,
                        temperature=0.4,
                    )
                    
                    response = completion.choices[0].message.content
                    
                    # Display assistant response in chat message container
                    with st.chat_message("assistant"):
                        st.markdown(response)
                    
                    # Add assistant response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    st.error(f"Error connecting to Groq API: {e}")
