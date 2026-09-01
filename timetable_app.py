import streamlit as st
import pandas as pd
import json, re, random, sys, requests
from ortools.sat.python import cp_model

st.set_page_config(page_title="Advanced Timetable Pro", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 API Keys Setup")
    st.markdown("Triple AI System (DeepSeek V4)")
    nvidia_api_key = st.text_input("Nvidia Master Key (nvapi-...)", type="password")

# --- AI HELPER ---
def call_nvidia(messages, temp=0.1, max_tokens=4000):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = nvidia_api_key.strip() if nvidia_api_key else ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-ai/deepseek-v4-pro-0813", "messages": messages, "temperature": temp, "max_tokens": max_tokens}
    res = requests.post(url, headers=headers, json=payload, timeout=320)
    if res.status_code != 200: raise Exception(f"API Error: {res.text}")
    return res.json()["choices"][0]["message"]["content"]

# --- RANGE PARSER ---
def parse_allowed(allowed_str, all_classes):
    s = str(allowed_str).strip()
    if not s or s.lower() == "all": return list(all_classes)
    m = re.search(r'(\d+)\s*[-_]?\s*([A-Za-z])\s*(?:to|-)\s*(\d+)\s*[-_]?\s*([A-Za-z])', s, re.I)
    if m:
        sg, eg = int(m.group(1)), int(m.group(3))
        return [c for c in all_classes if re.match(r'(\d+)', c) and sg <= int(re.match(r'(\d+)', c).group(1)) <= eg]
    return [c for c in all_classes if c.lower() in [x.strip().lower() for x in s.split(",")]]

# --- DATA PREP ---
def prepare_data():
    c_list = st.session_state.classes_df["Class Name"].dropna().tolist()
    t_list = st.session_state.teachers_df.to_dict("records")
    w_days = int(st.session_state.working_days)
    p_per_day = int(st.session_state.periods_per_day)
    break_at = int(st.session_state.break_at)
    is_half = st.session_state.saturday_half_day

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][:w_days]
    p_labels, v_periods, g_idx = [], [], 0
    for d in days:
        cur_p = 4 if (d.lower() == "saturday" and is_half) else p_per_day
        for p in range(1, cur_p + 1):
            g_idx += 1
            p_labels.append(f"{d} - P{p}")
            v_periods.append(g_idx)
            if p == break_at and not (d.lower() == "saturday" and is_half):
                p_labels.append(f"{d} - LUNCH")

    # Workload balance per subject
    sub_map = {}
    for t in t_list:
        sub = str(t.get("Subject", "")).strip()
        if not sub: continue
        p_cnt = int(t.get("Periods/Week (Per Class)", 4))
        if sub not in sub_map: sub_map[sub] = {"periods": p_cnt, "teachers": []}
        sub_map[sub]["teachers"].append({"name": t.get("Teacher Name", ""), "allowed": parse_allowed(t.get("Allowed Classes", ""), c_list), "load": 0})

    reqs = {c: [] for c in c_list}
    for sub, info in sub_map.items():
        for c in c_list:
            eligible = [t for t in info["teachers"] if c in t["allowed"]]
            if eligible:
                eligible.sort(key=lambda x: x["load"])
                chosen = eligible[0]
                chosen["load"] += info["periods"]
                for _ in range(info["periods"]): reqs[c].append((chosen["name"], sub))

    for c in c_list:
        while len(reqs[c]) < len(v_periods): reqs[c].append(("-", "Free Period"))
        if len(reqs[c]) > len(v_periods): reqs[c] = reqs[c][:len(v_periods)]

    return c_list, p_labels, v_periods, reqs

# --- STATE INIT ---
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 7
if "break_at" not in st.session_state: st.session_state.break_at = 4
if "saturday_half_day" not in st.session_state: st.session_state.saturday_half_day = False
if "classes_df" not in st.session_state: st.session_state.classes_df = pd.DataFrame({"Class Name": ["1-A", "1-B"]})
if "teachers_df" not in st.session_state:
    st.session_state.teachers_df = pd.DataFrame([
        {"Teacher Name": "Amit Sharma", "Subject": "English", "Allowed Classes": "1-A to 5-B", "Periods/Week (Per Class)": 4},
        {"Teacher Name": "Rahul Jain", "Subject": "Mathematics", "Allowed Classes": "1-A to 5-B", "Periods/Week (Per Class)": 5}
    ])
if "rules_df" not in st.session_state: st.session_state.rules_df = pd.DataFrame({"Rule": []})
if "ai3_msgs" not in st.session_state: st.session_state.ai3_msgs = []

st.title("🏫 Advanced Timetable Pro (Triple AI System)")

# --- TABS ---
t1, t2, t3, t4, t5 = st.tabs(["🕒 Timings", "🏫 Classes", "👨🏫 Teachers", "⚙️ Rules", "🚀 Engine & AI"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.working_days = st.number_input("Working Days", 1, 7, int(st.session_state.working_days))
        st.session_state.periods_per_day = st.number_input("Periods per Day", 1, 20, int(st.session_state.periods_per_day))
        st.session_state.break_at = st.number_input("Lunch After Period", 1, 15, int(st.session_state.break_at))
        st.session_state.saturday_half_day = st.checkbox("Saturday Half-Day?", value=st.session_state.saturday_half_day)
    with c2:
        slots = [{"Slot": f"P{i}", "Time": "45 Mins"} for i in range(1, int(st.session_state.periods_per_day)+1)]
        st.dataframe(pd.DataFrame(slots), use_container_width=True, hide_index=True)

with t2: st.session_state.classes_df = st.data_editor(st.session_state.classes_df, num_rows="dynamic", use_container_width=True)
with t3: st.session_state.teachers_df = st.data_editor(st.session_state.teachers_df, num_rows="dynamic", use_container_width=True)
with t4: st.session_state.rules_df = st.data_editor(st.session_state.rules_df, num_rows="dynamic", use_container_width=True)

with t5:
    col_l, col_r = st.columns([4, 6])
    with col_l:
        st.subheader("💬 AI Data Chat")
        user_input = st.text_area("Paste text/data here:", height=100)
        if st.button("Send to AI 1 🚀"):
            if not nvidia_api_key: st.error("Enter Nvidia API Key in sidebar!")
            else:
                with st.spinner("AI 1 Acknowledging..."):
                    try:
                        reply = call_nvidia([{"role": "system", "content": "Acknowledge receipt and say: '✅ Data ready! Click Sync Tabs to update.'"}, {"role": "user", "content": user_input}], max_tokens=100)
                        st.info(reply)
                    except Exception as e: st.error(str(e))

        if st.button("🔄 AI 2: Extract & Sync Tabs"):
            if not nvidia_api_key: st.error("Enter Nvidia API Key in sidebar!")
            else:
                with st.spinner("AI 2 extracting JSON data..."):
                    try:
                        sys_prompt = "Extract parameters into raw JSON: {\"working_days\": 6, \"periods_per_day\": 7, \"break_at\": 4, \"classes\": [\"1-A\"], \"teachers\": [{\"Teacher Name\": \"T1\", \"Subject\": \"S1\", \"Allowed Classes\": \"1-A to 5-B\", \"Periods/Week (Per Class)\": 4}], \"rules\": []}"
                        raw = call_nvidia([{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_input}])
                        raw = raw[raw.find("{"):raw.rfind("}")+1]
                        raw = re.sub(r',\s*}', '}', re.sub(r',\s*]', ']', raw))
                        data = json.loads(raw)
                        if "classes" in data: st.session_state.classes_df = pd.DataFrame({"Class Name": data["classes"]})
                        if "teachers" in data: st.session_state.teachers_df = pd.DataFrame(data["teachers"])
                        if "working_days" in data: st.session_state.working_days = int(data["working_days"])
                        if "periods_per_day" in data: st.session_state.periods_per_day = int(data["periods_per_day"])
                        if "break_at" in data: st.session_state.break_at = int(data["break_at"])
                        if "rules" in data: st.session_state.rules_df = pd.DataFrame({"Rule": data["rules"]})
                        st.success("🎉 Tabs Synced Successfully!")
                        st.rerun()
                    except Exception as e: st.error(f"Sync Error: {e}")

    with col_r:
        st.subheader("🔥 Timetable Generation Engine")
        if st.button("⚡ Generate Conflict-Free Timetable (OR-Tools)", type="primary", use_container_width=True):
            with st.spinner("Generating conflict-free timetable..."):
                try:
                    c_list, p_labels, v_periods, reqs = prepare_data()
                    model = cp_model.CpModel()
                    x = {c: {p: {r_idx: model.NewBoolVar(f"a_{c}_{p}_{r_idx}") for r_idx in range(len(reqs[c]))} for p in v_periods} for c in c_list}
                    for c in c_list:
                        for p in v_periods: model.AddExactlyOne([x[c][p][r_idx] for r_idx in range(len(reqs[c]))])
                        for r_idx in range(len(reqs[c])): model.AddExactlyOne([x[c][p][r_idx] for p in v_periods])

                    all_t = {req[0] for c in c_list for req in reqs[c] if req[0] != "-"}
                    for p in v_periods:
                        for t_name in all_t:
                            t_assigns = [x[c][p][r_idx] for c in c_list for r_idx, req in enumerate(reqs[c]) if req[0] == t_name]
                            if len(t_assigns) > 1: model.AddAtMostOne(t_assigns)

                    solver = cp_model.CpSolver()
                    solver.parameters.max_time_in_seconds = 15.0
                    status = solver.Solve(model)

                    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                        grid = {c: ["EMPTY"] * len(p_labels) for c in c_list}
                        for c in c_list:
                            for idx, lbl in enumerate(p_labels):
                                if "LUNCH" in lbl: grid[c][idx] = "LUNCH / BREAK"
                            for p in v_periods:
                                for r_idx, req in enumerate(reqs[c]):
                                    if solver.Value(x[c][p][r_idx]) == 1:
                                        p_idx = -1
                                        for idx, lbl in enumerate(p_labels):
                                            if "LUNCH" not in lbl:
                                                p_idx += 1
                                                if p_idx == p - 1:
                                                    grid[c][idx] = "Free Period" if req[0] == "-" else f"{req[1]} ({req[0]})"
                                                    break
                        df_res = pd.DataFrame(grid)
                        df_res.insert(0, "Day / Period", p_labels)
                        st.success(f"✅ Timetable Generated Successfully! (Status: {solver.StatusName(status)})")
                        st.dataframe(df_res, use_container_width=True, hide_index=True)
                    else:
                        st.error("❌ Deadlock detected. Use AI-3 Diagnostic below to troubleshoot.")
                except Exception as e:
                    st.error(f"Engine Error: {e}")

    st.markdown("---")
    st.subheader("🤖 Step 3: AI-3 Deadlock Diagnostics & Rule Fixer")
    ai3_txt = st.text_area("Ask AI-3 to troubleshoot / modify rules:")
    if st.button("Ask AI-3 🛠️"):
        if not nvidia_api_key: st.error("Enter Nvidia API Key!")
        else:
            with st.spinner("AI-3 Analyzing..."):
                try:
                    c_list, p_labels, v_periods, reqs = prepare_data()
                    live_str = json.dumps({"classes": c_list, "teachers": st.session_state.teachers_df.to_dict("records"), "rules": st.session_state.rules_df["Rule"].tolist()})
                    sys_p = f"You are AI-3 Timetable Diagnostics. DATA:\n{live_str}\nHelp user troubleshoot. If updating rules, end with: ```json\n{{\"updated_rules\": [\"Rule 1\"]}}\n```"
                    reply = call_nvidia([{"role": "system", "content": sys_p}, {"role": "user", "content": ai3_txt}])
                    st.markdown(re.sub(r'```json\s*\{.*?\}\s*```', '', reply, flags=re.DOTALL))
                    m = re.search(r'```json\s*(\{.*?\})\s*```', reply, re.DOTALL)
                    if m:
                        r_data = json.loads(m.group(1))
                        if "updated_rules" in r_data:
                            st.session_state.rules_df = pd.DataFrame({"Rule": r_data["updated_rules"]})
                            st.success("✅ Rules updated by AI-3!")
                            st.rerun()
                except Exception as e: st.error(f"AI-3 Error: {e}")
