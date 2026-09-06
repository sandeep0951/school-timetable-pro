import json
import random
import re
import sys
import time
from ortools.sat.python import cp_model
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Advanced Timetable Pro (Triple AI System)", layout="wide"
)

# ================= SIDEBAR =================
with st.sidebar:
  st.header("🔑 API Keys Setup")
  st.markdown(
      "Triple AI Architecture:\n1. Chat Collector: DeepSeek V4\n2. JSON Sync:"
      " DeepSeek V4\n3. Rule Fixer: DeepSeek V4\n4. **Interactive Custom"
      " Studio**"
  )
  nvidia_api_key = st.text_input(
      "Nvidia Master Key (nvapi-...)", type="password"
  )
  st.info("🛡️ Bina quotes ke API key dalein.")


# ================= AI HELPER =================
def call_nvidia(messages, temp=0.1, max_tokens=4000):
  url = "https://integrate.api.nvidia.com/v1/chat/completions"
  key = nvidia_api_key.strip() if nvidia_api_key else ""
  headers = {
      "Authorization": f"Bearer {key}",
      "Content-Type": "application/json",
  }
  payload = {
      "model": "deepseek-ai/deepseek-v4-pro-0813",
      "messages": messages,
      "temperature": temp,
      "max_tokens": max_tokens,
  }
  res = requests.post(url, headers=headers, json=payload, timeout=320)
  if res.status_code != 200:
    raise Exception(f"Nvidia API Error: {res.text}")
  return res.json()["choices"][0]["message"]["content"]


# ================= ROBUST JSON PARSER =================
def extract_json_safe(raw_text):
  if not raw_text:
    return None
  cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
  m = re.search(
      r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE
  )
  if m:
    try:
      return json.loads(m.group(1))
    except Exception:
      pass
  s_idx = cleaned.find("{")
  e_idx = cleaned.rfind("}")
  if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
    raw = cleaned[s_idx : e_idx + 1]
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)
    try:
      return json.loads(raw)
    except Exception:
      pass
  return None


# ================= ROBUST RANGE & CLASS PARSER =================
def parse_allowed_classes(allowed_str, all_classes):
  s = str(allowed_str).strip()
  if not s or s.lower() in ["all", "*", "any", ""]:
    return list(all_classes)

  tokens = [x.strip().lower() for x in re.split(r"[,;]", s) if x.strip()]
  matched = []
  for c in all_classes:
    c_clean = c.lower().replace(" ", "").replace("-", "").replace("th", "")
    for tok in tokens:
      tok_clean = tok.replace(" ", "").replace("-", "").replace("th", "")
      if tok_clean in c_clean or c.lower() == tok:
        matched.append(c)
        break

  range_match = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)", s, re.IGNORECASE)
  if range_match:
    sg = int(range_match.group(1))
    eg = int(range_match.group(2))
    for c in all_classes:
      m = re.search(r"(\d+)", c)
      if m and sg <= int(m.group(1)) <= eg:
        if c not in matched:
          matched.append(c)

  return matched if matched else list(all_classes)


# ================= CORE SUBJECT IDENTIFIER =================
def is_core_subject(subject_name):
  s = str(subject_name).lower().strip()
  core_keywords = [
      "math",
      "science",
      "social",
      "hindi",
      "english",
      "evs",
      "sst",
      "physics",
      "chemistry",
      "biology",
  ]
  return any(k in s for k in core_keywords)


# ================= TIMING HELPER =================
def update_timing_df(p_count=None, b_at=None):
  if p_count is None:
    p_count = int(st.session_state.get("periods_per_day", 7))
  if b_at is None:
    b_at = int(st.session_state.get("break_at", 4))
  slots = []
  for i in range(1, p_count + 1):
    slots.append({"Slot": f"Period {i}", "Duration (Mins)": 45})
    if i == b_at:
      slots.append({"Slot": "LUNCH BREAK", "Duration (Mins)": 30})
  return pd.DataFrame(slots)


# ================= DATA PREPARATION =================
def prepare_engine_data():
  sys.setrecursionlimit(5000)
  classes_list = st.session_state.classes_df["Class Name"].dropna().tolist()
  teachers_list = st.session_state.teachers_df.to_dict("records")
  w_days = int(st.session_state.working_days)
  p_per_day = int(st.session_state.periods_per_day)
  break_at = int(st.session_state.break_at)
  is_half = st.session_state.saturday_half_day

  days_str = [
      "Monday",
      "Tuesday",
      "Wednesday",
      "Thursday",
      "Friday",
      "Saturday",
  ][:w_days]
  period_labels = []
  valid_periods = []
  global_p_idx = 0

  for d in days_str:
    current_day_periods = (
        4 if (d.lower() == "saturday" and is_half) else p_per_day
    )
    for p in range(1, current_day_periods + 1):
      global_p_idx += 1
      period_labels.append(f"{d} - P{p}")
      valid_periods.append(global_p_idx)
      if p == break_at and not (d.lower() == "saturday" and is_half):
        period_labels.append(f"{d} - LUNCH")

  total_weekly_periods = len(valid_periods)
  initial_timetable = {c: ["EMPTY"] * len(period_labels) for c in classes_list}
  for c in classes_list:
    for idx, label in enumerate(period_labels):
      if "LUNCH" in label:
        initial_timetable[c][idx] = "LUNCH / BREAK"

  subjects_map = {}
  for t in teachers_list:
    sub = str(t.get("Subject", "")).strip()
    if not sub:
      continue
    try:
      p_count = int(t.get("Periods/Week (Per Class)", 4))
    except Exception:
      p_count = 4
    if sub not in subjects_map:
      subjects_map[sub] = {"periods": p_count, "teachers": []}
    subjects_map[sub]["teachers"].append({
        "name": t.get("Teacher Name", ""),
        "allowed": parse_allowed_classes(
            t.get("Allowed Classes", ""), classes_list
        ),
        "load": 0,
    })

  class_requirements = {c: [] for c in classes_list}
  for sub, info in subjects_map.items():
    p_count = info["periods"]
    teachers = info["teachers"]
    for c in classes_list:
      eligible = [t for t in teachers if c in t["allowed"]]
      if not eligible:
        continue
      eligible.sort(key=lambda x: x["load"])
      chosen = eligible[0]
      chosen["load"] += p_count
      for _ in range(p_count):
        class_requirements[c].append((chosen["name"], sub))

  for c in classes_list:
    req_pool = list(class_requirements[c])
    idx = 0
    while len(class_requirements[c]) < total_weekly_periods:
      if req_pool:
        class_requirements[c].append(req_pool[idx % len(req_pool)])
        idx += 1
      else:
        class_requirements[c].append(("-", "Free Period"))
    if len(class_requirements[c]) > total_weekly_periods:
      class_requirements[c] = class_requirements[c][:total_weekly_periods]

  return (
      classes_list,
      period_labels,
      valid_periods,
      initial_timetable,
      class_requirements,
  )


# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state:
  st.session_state["working_days"] = 6
if "periods_per_day" not in st.session_state:
  st.session_state["periods_per_day"] = 7
if "break_at" not in st.session_state:
  st.session_state["break_at"] = 4
if "saturday_half_day" not in st.session_state:
  st.session_state["saturday_half_day"] = False
if "sync_id" not in st.session_state:
  st.session_state.sync_id = 0

if "periods_timing_df" not in st.session_state:
  st.session_state.periods_timing_df = update_timing_df(7, 4)

if "classes_df" not in st.session_state:
  st.session_state.classes_df = pd.DataFrame({"Class Name": ["1-A", "1-B"]})

if "teachers_df" not in st.session_state:
  st.session_state.teachers_df = pd.DataFrame([
      {
          "Teacher Name": "Amit Sharma",
          "Subject": "English",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 6,
      },
      {
          "Teacher Name": "Rahul Jain",
          "Subject": "Mathematics",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 6,
      },
      {
          "Teacher Name": "Rajesh Singh",
          "Subject": "Hindi",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 6,
      },
      {
          "Teacher Name": "Kavita Joshi",
          "Subject": "Science",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 6,
      },
      {
          "Teacher Name": "Rakesh Gupta",
          "Subject": "Social Science",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 6,
      },
      {
          "Teacher Name": "Karan Malhotra",
          "Subject": "Computer",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 3,
      },
      {
          "Teacher Name": "Priyanka Yadav",
          "Subject": "Art & Craft",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 3,
      },
      {
          "Teacher Name": "Ravi Joshi",
          "Subject": "Physical Education",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 3,
      },
      {
          "Teacher Name": "Nisha Patel",
          "Subject": "Library",
          "Allowed Classes": "all",
          "Periods/Week (Per Class)": 3,
      },
  ])

if "rules_df" not in st.session_state:
  st.session_state.rules_df = pd.DataFrame({
      "Rule": [
          "Core subjects (Maths, Science, SST, Hindi, English) daily minimum 1"
          " period.",
          (
              "Other activities (Computer, Sports, Library, Art) different days"
              " par rotate hon."
          ),
          "No teacher conflict and no consecutive same subjects.",
      ]
  })

if "chat_messages" not in st.session_state:
  st.session_state.chat_messages = []

if "day_rules_df" not in st.session_state:
  st.session_state.day_rules_df = pd.DataFrame(
      columns=["Day", "Rule Type", "Target", "Value", "Status"]
  )

if "manual_grids" not in st.session_state:
  st.session_state.manual_grids = {}

st.title("🏫 Advanced Timetable Pro (Triple AI System)")

# ================= UI TABS =================
tab1, tab2, tab3, tab4, tab5, tab_custom = st.tabs([
    "🕒 Timings",
    "🏫 Classes",
    "👨🏫 Teachers",
    "⚙️ Rules",
    "🚀💬 AI & Engine Center",
    "📅 Day-by-Day Custom Studio",
])

# ================= TAB 1: TIMINGS =================
with tab1:
  col1, col2 = st.columns(2)
  with col1:
    wd = st.number_input(
        "1. Working Days",
        min_value=1,
        max_value=7,
        value=int(st.session_state.working_days),
        key=f"wd_key_{st.session_state.sync_id}",
    )
    ppd = st.number_input(
        "2. Periods per Day",
        min_value=1,
        max_value=20,
        value=int(st.session_state.periods_per_day),
        key=f"ppd_key_{st.session_state.sync_id}",
    )
    brk = st.number_input(
        "Lunch Break AFTER period?",
        min_value=1,
        max_value=15,
        value=int(st.session_state.break_at),
        key=f"brk_key_{st.session_state.sync_id}",
    )
    sat = st.checkbox(
        "4. Saturday Half-Day?",
        value=bool(st.session_state.saturday_half_day),
        key=f"sat_key_{st.session_state.sync_id}",
    )
    st.session_state.working_days = wd
    st.session_state.periods_per_day = ppd
    st.session_state.break_at = brk
    st.session_state.saturday_half_day = sat

  with col2:
    st.subheader("Period Timings & Duration")
    expected_slots = int(st.session_state.periods_per_day) + (
        1 if int(st.session_state.break_at) > 0 else 0
    )
    if len(st.session_state.periods_timing_df) != expected_slots:
      st.session_state.periods_timing_df = update_timing_df(
          int(st.session_state.periods_per_day), int(st.session_state.break_at)
      )
    st.session_state.periods_timing_df = st.data_editor(
        st.session_state.periods_timing_df,
        use_container_width=True,
        hide_index=True,
        key=f"time_editor_{st.session_state.sync_id}",
    )

# ================= TAB 2: CLASSES =================
with tab2:
  st.subheader("🏫 Classes List")
  st.session_state.classes_df = st.data_editor(
      st.session_state.classes_df,
      num_rows="dynamic",
      use_container_width=True,
      key=f"classes_editor_{st.session_state.sync_id}",
  )

# ================= TAB 3: TEACHERS =================
with tab3:
  st.subheader("👨🏫 Teachers & Subject Allotment")
  st.session_state.teachers_df = st.data_editor(
      st.session_state.teachers_df,
      num_rows="dynamic",
      use_container_width=True,
      key=f"teachers_editor_{st.session_state.sync_id}",
  )

# ================= TAB 4: RULES =================
with tab4:
  st.subheader("⚙️ Institutional Rules")
  st.session_state.rules_df = st.data_editor(
      st.session_state.rules_df,
      num_rows="dynamic",
      use_container_width=True,
      key=f"rules_editor_{st.session_state.sync_id}",
  )

# ================= TAB 5: AI & ENGINE CENTER =================
with tab5:
  st.markdown("### 🛠️ Step 1 & 2: Setup Data & Run Engine")
  col_chat, col_engine = st.columns([4, 6], gap="large")

  with col_chat:
    st.subheader("💬 AI-1 Data Collector")
    chat_box = st.container(height=250)
    with chat_box:
      for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
          st.markdown(m["content"])

    with st.form("chat_form", clear_on_submit=True):
      user_text = st.text_area("Paste Data Here:", height=80)
      btn_c1, btn_c2 = st.columns([7, 3])
      with btn_c1:
        submit_msg = st.form_submit_button("Send Data 🚀")
      with btn_c2:
        if st.form_submit_button("🗑️ Clear"):
          st.session_state.chat_messages = []
          st.rerun()

    if submit_msg and user_text:
      if not nvidia_api_key:
        st.error("❌ Key Missing in Sidebar!")
      else:
        st.session_state.chat_messages.append(
            {"role": "user", "content": user_text}
        )
        with chat_box:
          with st.chat_message("user"):
            st.markdown(user_text)
        with st.spinner("AI 1 Acknowledging..."):
          try:
            sys_prompt = (
                "You are a receptionist. Acknowledge receipt and say: '✅ Data"
                " is ready! Please click the Sync Button to update tabs.' DO"
                " NOT generate timetable."
            )
            reply = call_nvidia(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=2500,
            )
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": reply}
            )
            with chat_box:
              with st.chat_message("assistant"):
                st.markdown(reply)
          except Exception as e:
            st.error(f"AI 1 Error: {e}")

  with col_engine:
    st.subheader("🔄 AI-2 & Engine Runner")
    if st.button("🔄 AI 2: Extract & Sync Tabs", use_container_width=True):
      if not nvidia_api_key:
        st.error("❌ Key Missing in Sidebar!")
      else:
        all_msgs = [
            m["content"]
            for m in st.session_state.chat_messages
            if m["role"] == "user"
        ]
        full_input = "\n\n".join(all_msgs)
        if len(full_input.strip()) < 10:
          st.warning(
              "⚠️ Pehle chat box mein apna school data paste karke 'Send Data'"
              " dabayein!"
          )
        else:
          with st.spinner(
              "AI 2 JSON bana raha hai aur tabs update kar raha hai..."
          ):
            try:
              sys_p = r"""You are a strict JSON data extractor. Extract timetable parameters from the text and output ONLY RAW JSON matching this exact schema:
{
  "working_days": 6,
  "periods_per_day": 7,
  "break_at": 4,
  "saturday_half_day": false,
  "classes": ["1-A", "1-B"],
  "teachers": [
    {
      "Teacher Name": "Amit Sharma",
      "Subject": "English",
      "Allowed Classes": "all",
      "Periods/Week (Per Class)": 6
    }
  ],
  "fixed_rules": ["Rule 1"]
}"""
              raw_out = call_nvidia(
                  [
                      {"role": "system", "content": sys_p},
                      {"role": "user", "content": full_input},
                  ],
                  temp=0.0,
                  max_tokens=4096,
              )
              data = extract_json_safe(raw_out)
              if data:
                # 1. Update basic timings directly in session state
                if "working_days" in data:
                  st.session_state["working_days"] = int(data["working_days"])
                if "periods_per_day" in data:
                  st.session_state["periods_per_day"] = int(
                      data["periods_per_day"]
                  )
                if "break_at" in data:
                  st.session_state["break_at"] = int(data["break_at"])
                if "saturday_half_day" in data:
                  st.session_state["saturday_half_day"] = (
                      str(data["saturday_half_day"]).lower() == "true"
                  )

                # 2. Update timings table automatically
                st.session_state.periods_timing_df = update_timing_df(
                    int(st.session_state["periods_per_day"]),
                    int(st.session_state["break_at"]),
                )

                # 3. Normalize and update classes
                if "classes" in data and data["classes"]:
                  c_list = data["classes"]
                  clean_classes = []
                  for item in c_list:
                    if isinstance(item, dict):
                      clean_classes.append(
                          str(
                              item.get("Class Name")
                              or item.get("name")
                              or list(item.values())[0]
                          )
                      )
                    else:
                      clean_classes.append(str(item))
                  st.session_state.classes_df = pd.DataFrame(
                      {"Class Name": clean_classes}
                  )

                # 4. Normalize and update teachers with strict headers
                if "teachers" in data and data["teachers"]:
                  normalized_teachers = []
                  for t in data["teachers"]:
                    if isinstance(t,
