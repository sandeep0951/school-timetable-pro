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
st.set_page_config(page_title="Advanced Timetable Pro (Weekly Edition)", layout="wide")

# Initialize Groq Client
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_api_key)
except:
    client = None

# App Header
st.title("🏫 Advanced Timetable Pro (Full Weekly Engine)")
st.markdown("Tier 1: Custom Python Logic | Tier 2: Google OR-Tools | AI Assistant")

if not ORTOOLS_AVAILABLE:
    st.warning("⚠️ Google 'ortools' is not installed. The app will only use the Custom Python Engine. Add 'ortools' to requirements.txt for the enterprise fallback.")

# --- INITIALIZE SESSION STATES FOR 2-WAY SYNC ---
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 8
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "periods_timing_df" not in st.session_state:
    slots = [{"Slot": f"Period {i}", "Duration (Mins)": 40} for i in range(1, 9)]
    slots.insert(4, {"Slot": "LUNCH BREAK", "Duration (Mins)": 40})
    st.session_state.periods_timing_df = pd.DataFrame(slots)

if "classes_df" not in st.session_state: 
    st.session_state.classes_df = pd.DataFrame({"Class Name": ["1st A", "1st B", "6th A", "9th A", "11th Sci"]})
if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame({
        "Teacher Name": ["Mr. Rohan Das", "Coach Ravi", "Mrs. Anita Sharma"],
        "Subject": ["Maths", "Sports", "English"],
        "Allowed Classes": ["All", "All", "1st A, 1st B"]
    })
if "fixed_rules" not in st.session_state: 
    st.session_state.fixed_rules = []

# --- TAB LAYOUT ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🕒 1. Timings & Days", 
    "🏫 2. Classes", 
    "👨‍🏫 3. Teachers", 
    "⚙️ 4. Rules", 
    "🚀💬 5. AI Co-Pilot & Engine"
])

# ==========================================
# TABS 1-4 (SYNCED WITH AI UI)
# ==========================================
with tab1:
    st.header("Weekly Schedule & Periods Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.working_days = st.number_input("Working Days per Week (e.g., Mon-Sat = 6)", min_value=1, max_value=7, value=int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("Periods per Day", min_value=1, max_value=20, value=int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch Break happens AFTER which period?", min_value=1, max_value=15, value=int(st.session_state.break_at))
    
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
# TAB 5: UNIFIED DASHBOARD (CHAT + ENGINE)
# ==========================================
with tab5:
    col_chat, col_engine = st.columns([4, 6], gap="large")
    
    # ------------------------------------------
    # LEFT COLUMN: AI CO-PILOT CHAT
    # ------------------------------------------
    with col_chat:
        col_c1, col_c2 = st.columns([7, 3])
        with col_c1:
            st.subheader("💬 AI Co-Pilot")
        with col_c2:
            if st.button("🗑️ Clear Chat"):
                del st.session_state["chat_messages"]
                st.rerun()

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {
                    "role": "system", 
                    "content": (
                        "You are a strict Timetable Data Collector.\n"
                        "Extract the user's data EXACTLY into these 8 points:\n"
                        "1. Working days per week & School timing\n"
                        "2. Periods per day\n"
                        "3. Lunch break\n"
                        "4. Total classes + sections\n"
                        "5. Total subjects\n"
                        "6. Total teacher (Naam, Subject, Classes)\n"
                        "7. Total other activity\n"
                        "8. Total rules\n\n"
                        "PROCESS:\n"
                        "If user sends data in PARTS, say: 'Data saved, please provide the next part'.\n"
                        "DO NOT stop if a teacher has 32 classes, because the engine now runs a WEEKLY schedule. "
                        "Just format the points cleanly."
                    )
                },
                {
                    "role": "assistant", 
                    "content": "Namaste Sandeep Sir! Engine ab 'Weekly' ho gaya hai. Aap apna poora data (Part 1, Part 2 karke) yahan daaliye. Koi problem nahi aayegi!"
                }
            ]

        chat_container = st.container(height=550)
        
        with chat_container:
            for message in st.session_state.chat_messages:
                if message["role"] != "system":
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        if prompt := st.chat_input("Apna instruction yahan likhein..."):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            if not client:
                st.error("❌ Groq API Key missing!")
            else:
                with st.spinner("AI data samajh raha hai..."):
                    try:
                        messages_to_send = [st.session_state.chat_messages[0]]
                        if len(st.session_state.chat_messages) > 3:
                            messages_to_send.extend(st.session_state.chat_messages[-2:])
                        else:
                            messages_to_send.extend(st.session_state.chat_messages[1:])
                            
                        completion = client.chat.completions.create(
                            model="llama-3.1-8b-instant",  
                            messages=messages_to_send,
                            temperature=0.3,
                            max_tokens=450 
                        )
                        
                        response = completion.choices[0].message.content
                        
                        with chat_container:
                            with st.chat_message("assistant"):
                                st.markdown(response)
                        
                        st.session_state.chat_messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        st.error(f"Error connecting to Groq API: {e}")

    # ------------------------------------------
    # RIGHT COLUMN: WEEKLY GENERATION ENGINE
    # ------------------------------------------
    with col_engine:
        st.subheader("⚙️ Action Center & Engine")
        
        if st.button("🔄 1. Sync AI Rules from Chat", use_container_width=True):
            if not client:
                st.error("Groq API Key missing!")
            elif "chat_messages" not in st.session_state or len(st.session_state.chat_messages) <= 2:
                st.warning("⚠️ Pehle AI se kuch rules discuss karein (Left side mein)!")
            else:
                with st.spinner("Translating Weekly Data into UI Format..."):
                    clean_history = []
                    for msg in st.session_state.chat_messages:
                        if msg["role"] == "user":
                            clean_history.append(f"User: {msg['content']}")
                    
                    chat_history = "\n".join(clean_history[-5:])

                    extraction_prompt = (
                        "Extract the user's timetable data into JSON.\n"
                        'Format EXACTLY like this JSON:\n'
                        '{"working_days":6,"periods_per_day":8,"break_at":4,"classes":["1st A", "1st B"],"teachers":[{"Teacher Name":"Balram","Subject":"Sanskrit","Allowed Classes":"All"}],"fixed_rules":[]}\n\n'
                        "Data to parse:\n" + chat_history
                    )
                    
                    try:
                        completion = client.chat.completions.create(
                            model="llama-3.1-8b-instant",  
                            messages=[{"role": "user", "content": extraction_prompt}],
                            temperature=0.1,
                            response_format={"type": "json_object"},
                            max_tokens=4000 
                        )
                        
                        raw_output = completion.choices[0].message.content
                        
                        clean_output = raw_output.strip()
                        if clean_output.startswith("```json"):
                            clean_output = clean_output.replace("```json", "", 1)
                            if clean_output.endswith("```"):
                                clean_output = clean_output[:-3]
                        elif clean_output.startswith("```"):
                            clean_output = clean_output.replace("```", "", 1)
                            if clean_output.endswith("
