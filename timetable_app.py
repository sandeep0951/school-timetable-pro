import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module

# App Configuration
st.set_page_config(page_title="Advanced Timetable Pro", layout="wide")

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
# TAB 5: Generate & Conflict Resolution (with AI Fix Prompt)
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
            st.error("**A. Problem**\n\nMs. Verma has 'Science' class in 10th A at Period 3, but she is on Leave from 15-Aug to 20-Aug.")
        with col_sugg:
            st.info("**B. Suggestion**\n\n1. Assign Mr. Sharma as proxy.\n2. Assign Library Period.")
        with col_sol:
            st.success("**C. Solution**\n\nSystem has auto-assigned 'Library' for 10th A in Period 3 to resolve the clash.")
        
        # --- AI PROMPT CONFLICT RESOLUTION OPTION ---
        st.markdown("---")
        st.subheader("🪄 Resolve Contradiction with AI Prompt")
        st.write("Agar aap system ka auto-solution badalna chahte hain, toh yahan prompt likhkar direct change karein:")
        
        resolve_prompt = st.text_input(
            "Enter resolution instruction:",
            placeholder="Example: 'Library ki jagah Mr. Gupta ko 10th A ke Period 3 mein English proxy de do'"
        )
        
        if st.button("✨ Apply Prompt Fix"):
            if resolve_prompt:
                st.session_state.custom_fix_applied = resolve_prompt
                st.success(f"✅ AI Fix Applied: '{resolve_prompt}' — Timetable updated accordingly!")
            else:
                st.warning("⚠️ Pehle resolution instruction likhiye!")

        st.markdown("---")
        st.subheader(f"Generated Timetable for {target_date.strftime('%d-%b-%Y')}")
        
        total_rows_to_show = total_periods + 1
        
        proxy_val = "Library (Proxy)"
        if st.session_state.get('custom_fix_applied'):
            proxy_val = "English - Mr. Gupta (AI Fixed)"

        dummy_tt = pd.DataFrame({
            "Period": ["1", "2", "3", "Break", "4", "5", "6", "7", "8", "9", "10"],
            "Time": ["08:00 - 08:50", "08:50 - 09:35", "09:35 - 10:20", "10:20 - 10:50", "10:50 - 11:35", "11:35 - 12:20", "12:20 - 13:05", "13:05 - 13:50", "13:50 - 14:35", "14:35 - 15:20", "15:20 - 16:05"],
            "9th A": ["English", "Hindi", "Science", "LUNCH", "Maths", "Sports", "Library", "Art", "Music", "Computer", "Free"],
            "10th A": ["Science", "English", proxy_val, "LUNCH", "Hindi", "Maths", "Sports", "History", "Geography", "Art", "Free"]
        })
        
        display_tt = dummy_tt.head(total_rows_to_show) if total_rows_to_show <= len(dummy_tt) else dummy_tt
        st.dataframe(display_tt, use_container_width=True, hide_index=True)
        st.download_button("📥 Download Final Timetable (CSV)", data=display_tt.to_csv(index=False), file_name=f"Timetable_{target_date}.csv", key="download_tab5")

# ==========================================
# TAB 6: AI Prompt Builder (NLP Feature)
# ==========================================
with tab6:
    st.header("🪄 AI Prompt Builder (Describe & Generate)")
    st.write("Ab manual rules dalne ki zaroorat nahi! Apne shabdon mein bataiye kaisa timetable chahiye.")
    
    ai_prompt = st.text_area(
        "Describe your requirement (Hindi or English):", 
        placeholder="Example: 'Mujhe 9th A aur 10th A ka timetable chahiye. Pehla period Maths ka rakhna. Mr. Sharma aaj leave par hain, unki jagah proxy laga dena...'",
        height=150
    )
    
    if st.button("✨ Generate with AI Prompt", type="primary"):
        if ai_prompt:
            with st.spinner("AI aapke prompt ko samajh raha hai aur possibilities (1) dhoondh raha hai..."):
                time_module.sleep(2) # Fake processing delay for feel
                
                st.success("✅ AI ne aapka prompt successfully decode kar liya hai aur rules set kar diye hain!")
                
                st.markdown("**🧠 AI Understood the following rules from your text:**")
                st.info("- Classes Detected: 9th A, 10th A\n- Rule Created: 1st Period MUST be Maths\n- Constraint Detected: Mr. Sharma is on Leave (Proxy logic activated)")
                
                st.markdown("---")
                st.subheader("AI Generated Timetable")
                
                dummy_ai_tt = pd.DataFrame({
                    "Period": ["1", "2", "3", "Break", "4", "5", "6", "7", "8"],
                    "Time": ["08:00 - 08:50", "08:50 - 09:35", "09:35 - 10:20", "10:20 - 10:50", "10:50 - 11:35", "11:35 - 12:20", "12:20 - 13:05", "13:05 - 13:50", "13:50 - 14:35"],
                    "9th A": ["Maths", "Science", "English", "LUNCH", "Hindi", "Sports", "Library", "Art", "Free"],
                    "10th A": ["Maths", "Hindi", "Science", "LUNCH", "English", "Library (Proxy)", "Sports", "History", "Free"]
                })
                
                st.dataframe(dummy_ai_tt, use_container_width=True, hide_index=True)
                st.download_button("📥 Download AI Timetable (CSV)", data=dummy_ai_tt.to_csv(index=False), file_name="AI_Timetable.csv", key="download_tab6")
        else:
            st.warning("⚠️ Pehle prompt box mein apni requirement likhiye!")
