import streamlit as st
import pandas as pd
from datetime import datetime, time
import time as time_module
import json
import random
import sys
import copy
import re
import requests

try:
    from ortools.sat.python import cp_model
    ORTOLS_AVAILABLE = True
except ImportError:
    ORTOLS_AVAILABLE = False

st.set_page_config(page_title="Advanced Timetable Pro (Triple AI System)", layout="wide")

# ================= SECRETS BYPASS (SIDEBAR) =================
with st.sidebar:
    st.header("🔑 API Keys Setup")
    st.markdown("Triple AI Architecture:\n1. Data Setup: DeepSeek V4\n2. JSON Sync: DeepSeek V4\n3. Rule Fixer: DeepSeek V4")
    nvidia_api_key = st.text_input("Nvidia Master Key (nvapi-...)", type="password")
    if ORTOLS_AVAILABLE:
        st.success("✅ Google OR-Tools is Active!")
    else:
        st.error("❌ Google OR-Tools is Missing!")
    st.info("🛡️ Bina double quotes ke key dalein.")

# ================= TRIPLE AI FUNCTIONS =================

# AI 1: Fast Chat Collector
def chat_ai(messages):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    system_instruction = {
        "role": "system",
        "content": "You are a receptionist. Acknowledge data and say: '✅ Data is ready. Please click the Sync Button to update tabs.' DO NOT generate timetable."
    }
    safe_messages = [system_instruction] + [m for m in messages if m.get("role") != "system"]
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": safe_messages,
        "temperature": 0.1,
        "max_tokens": 2500
    }
    response = requests.post(url, headers=headers, json=payload, timeout=300)
    if response.status_code != 200:
        raise Exception(f"Chat AI Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# AI 2: JSON Expert
def json_ai(prompt_text):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are a strict JSON data extractor. Extract timetable parameters from the text and output ONLY RAW JSON. "
        "CRITICAL RULES: \n"
        "1. DO NOT invent data. Use ONLY the data provided.\n"
        "2. Ensure all arrays are properly closed.\n"
        "3. EXTRACT ALL RULES and put them in the 'fixed_rules' array.\n"
        "4. Format exactly like this:\n"
        "{\n"
        '  "working_days": 6,\n'
        '  "periods_per_day": 7,\n'
        '  "break_at": 4,\n'
        '  "saturday_half_day": false,\n'
        '  "classes": ["1-A", "1-B"],\n'
        '  "teachers": [{"Teacher Name": "Amit Sharma", "Subject": "English", "Allowed Classes": "1-A, 1-B", "Periods/Week (Per Class)": 4}],\n'
        '  "fixed_rules": ["Rule 1: No double booking"]\n'
        "}"
    )
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.0,
        "max_tokens": 4096
    }
    response = requests.post(url, headers=headers, json=payload, timeout=300)
    if response.status_code != 200:
        raise Exception(f"JSON AI Error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# AI 3: Interactive Diagnostics & Rule Fixer
def chat_ai3(user_input, current_data_str, history):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are 'AI-3', an expert Timetable Diagnostics and Rule Fixer AI. "
        "You help the user troubleshoot why their Timetable Engine (OR-Tools) is failing (Deadlock). "
        "You communicate in friendly Hinglish (Hindi + English).\n\n"
        f"CURRENT LIVE APP DATA (From Tabs):\n{current_data_str}\n\n"
        "YOUR DUTIES:\n"
        "1. DIAGNOSE: Analyze the data above. Look for bottlenecks. Explain clearly WHY OR-Tools failed.\n"
        "2. SUGGEST: Provide 2-3 bullet points on what needs to be changed.\n"
        "3. RULE MODIFICATION: Output updated rules inside a JSON block at the end:\n"
        "```json\n"
        "{\n"
        '  "updated_rules": ["Rule 1", "Rule 2"]\n'
        "}\n"
        "```"
    )
    messages = [{"role": "system", "content": system_prompt}] + history
    messages.append({"role": "user", "content": user_input})
    payload = {
        "model": "deepseek-ai/deepseek-v4-pro-0813",
        "messages": messages,
        "temperature
