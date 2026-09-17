import streamlit as st
import pandas as pd
import datetime
import io
from ortools.sat.python import cp_model

st.set_page_config(page_title="School Timetable Pro (Fully Dynamic Breaks & Schedule)", layout="wide", page_icon="🏫")

# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 7
if "period_duration" not in st.session_state: st.session_state.period_duration = 40
if "school_start_time" not in st.session_state: st.session_state.school_start_time = datetime.time(8, 0)

if "num_breaks" not in st.session_state: st.session_state.num_breaks = 2

# Store dynamic breaks list in session state
if "breaks_data" not in st.session_state:
    st.session_state.breaks_data = [
        {"name": "☕ Morning Recess", "after_period": 2, "duration": 15},
        {"name": "🍱 Lunch Break", "after_period": 4, "duration": 35},
        {"name": "🥛 Afternoon Snack Break", "after_period": 6, "duration": 15},
        {"name": "🍎 Fruit Break", "after_period": 1, "duration": 10},
        {"name": "⚽ Evening Recess", "after_period": 7, "duration": 20},
    ]

if "classes_list" not in st.session_state:
    st.session_state.classes_list = ["6-A", "6-B", "7-A", "7-B"]

if "allotments_df" not in st.session_state:
    sample_subs = [
        ("Mathematics", 6, {"6-A": "Nikum Sir", "6-B": "Nikum Sir", "7-A": "Rahul Sir", "7-B": "Rahul Sir"}),
        ("Science", 6, {"6-A": "Ashok Sir", "6-B": "Ashok Sir", "7-A": "Kavita Mam", "7-B": "Kavita Mam"}),
        ("English", 6, {"6-A": "Sandip Sir", "6-B": "Usha Mam", "7-A": "Sandip Sir", "7-B": "Usha Mam"}),
        ("Hindi", 6, {"6-A": "Apeksha Mam", "6-B": "Apeksha Mam", "7-A": "Rajesh Sir", "7-B": "Rajesh Sir"}),
        ("Social Studies", 6, {"6-A": "Rudra Sir", "6-B": "Rudra Sir", "7-A": "Rakesh Sir", "7-B": "Rakesh Sir"}),
        ("Sanskrit", 6, {"6-A": "Padma Mam", "6-B": "Padma Mam", "7-A": "Padma Mam", "7-B": "Padma Mam"}),
        ("Sports", 6, {"6-A": "Vikram Sir", "6-B": "Vikram Sir", "7-A": "Vikram Sir", "7-B": "Vikram Sir"}),
    ]
    st.session_state.allotments_df = pd.DataFrame([
        {"Class": c, "Subject": sub, "Teacher": t_map[c], "Periods/Week": p}
        for sub, p, t_map in sample_subs for c in ["6-A", "6-B", "7-A", "7-B"]
    ])

if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = None

# ================= HELPER FUNCTIONS =================
def calculate_bell_schedule(start_time_obj, period_duration_mins, total_periods, breaks_list):
    """दैनिक समय सारिणी (Start Time, End Time) की पूरी टाइमलाइन की गणना करता है (0, 1, 2, 3 या कितने भी ब्रेक्स के साथ)"""
    cur_time = datetime.datetime.combine(datetime.date.today(), start_time_obj)
    timeline = []
    
    # Sort breaks by after_period
    sorted_breaks = sorted(breaks_list, key=lambda x: int(x["after_period"]))
    breaks_map = {}
    for b in sorted_breaks:
        p_num = int(b["after_period"])
        if p_num not in breaks_map:
            breaks_map[p_num] = []
        breaks_map[p_num].append(b)
        
    for p in range(1, total_periods + 1):
        p_start = cur_time
        cur_time += datetime.timedelta(minutes=int(period_duration_mins))
        p_end = cur_time
        time_str = f"{p_start.strftime('%I:%M')}-{p_end.strftime('%I:%M %p')}"
        timeline.append({
            "type": "period",
            "period_num": p,
            "label": f"Period {p}",
            "time_str": time_str,
            "header": f"Period {p}\n({time_str})",
            "excel_header": f"Period {p} ({time_str})"
        })
        
        if p in breaks_map:
            for brk in breaks_map[p]:
                b_start = cur_time
                cur_time += datetime.timedelta(minutes=int(brk["duration"]))
                b_end = cur_time
                b_time_str = f"{b_start.strftime('%I:%M')}-{b_end.strftime('%I:%M %p')}"
                timeline.append({
                    "type": "break",
                    "period_num": None,
                    "label": brk["name"],
                    "time_str": b_time_str,
                    "header": f"{brk['name']}\n({b_time_str})",
                    "excel_header": f"{brk['name']} ({b_time_str})"
                })
                
    dismissal_time = cur_time.strftime("%I:%M %p")
    return timeline, dismissal_time

def normalize_allotment_df(df):
    col_map = {}
    for col in df.columns:
        c_clean = str(col).strip().lower().replace(" ", "").replace("_", "").replace("/", "")
        if any(k in c_clean for k in ["class", "grade", "section"]):
            col_map[col] = "Class"
        elif any(k in c_clean for k in ["subject", "sub"]):
            col_map[col] = "Subject"
        elif any(k in c_clean for k in ["teacher", "faculty", "staff", "instructor"]):
            col_map[col] = "Teacher"
        elif any(k in c_clean for k in ["period", "count", "quota", "slot"]):
            col_map[col] = "Periods/Week"
    
    df = df.rename(columns=col_map)
    required = ["Class", "Subject", "Teacher", "Periods/Week"]
    for req in required:
        if req not in df.columns:
            if req == "Periods/Week": df[req] = 4
            else: df[req] = ""
            
    for c in ["Class", "Subject", "Teacher"]:
        df[c] = df[c].astype(str).str.strip()
    
    df = df[~df["Class"].str.lower().isin(["", "nan", "none"])]
    df = df[~df["Subject"].str.lower().isin(["", "nan", "none"])]
    df = df[~df["Teacher"].str.lower().isin(["", "nan", "none"])]
    
    df["Periods/Week"] = pd.to_numeric(df["Periods/Week"], errors="coerce").fillna(4).astype(int).clip(lower=1)
    return df[required].reset_index(drop=True)

def pre_check_allotments(df_allot, classes, slots_per_class):
    issues = []
    warnings = []
    
    for c in classes:
        sub_df = df_allot[df_allot["Class"] == c]
        total_req = sub_df["Periods/Week"].sum()
        if total_req > slots_per_class:
            issues.append(f"Class '{c}': कुल माँगे गए {total_req} पीरियड, जबकि उपलब्ध केवल {slots_per_class} स्लॉट्स हैं।")
    
    teacher_totals = df_allot[df_allot["Teacher"] != "Supervised Activity"].groupby("Teacher")["Periods/Week"].sum()
    for t, total_periods in teacher_totals.items():
        if total_periods > slots_per_class:
            issues.append(f"Teacher '{t}': कुल {total_periods} पीरियड असाइन हुए हैं, जो हफ़्ते की अधिकतम सीमा ({slots_per_class} स्लॉट्स) से ज़्यादा हैं।")
        elif total_periods >= int(slots_per_class * 0.9):
            warnings.append(f"Teacher '{t}': {total_periods}/{slots_per_class} स्लॉट्स (अत्यधिक लोड - {round(total_periods/slots_per_class*100)}%)")
            
    return issues, warnings

def generate_master_excel(sch):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        # Sheet 1: Master Timetable
        all_classes_data = []
        for c in sch["classes"]:
            for d in sch["days"]:
                row = {"Class": c, "Day": d}
                for item in sch["timeline"]:
                    h_name = item["excel_header"]
                    if item["type"] == "break":
                        row[h_name] = item["label"]
                    else:
                        p = item["period_num"]
                        subj, teacher = sch["schedule"].get((c, d, p), ("-", "-"))
                        row[h_name] = f"{subj} ({teacher})"
                all_classes_data.append(row)
        pd.DataFrame(all_classes_data).to_excel(writer, sheet_name="Master Timetable", index=False)
        
        # Sheet 2: Teacher Workload Summary
        workload = []
        for t in sorted(sch["teachers"]):
            cnt = sum(1 for (c, d, p), (subj, t_assigned) in sch["schedule"].items() if t_assigned == t)
            workload.append({"Teacher Name": t, "Weekly Teaching Periods": cnt, "Daily Avg": round(cnt / len(sch["days"]), 2)})
        pd.DataFrame(workload).to_excel(writer, sheet_name="Teacher Workload", index=False)

    buf.seek(0)
    return buf.getvalue()

# ================= OR-TOOLS SOLVER ENGINE =================
def solve_school_timetable(timeline, dismissal_time, time_limit=15.0):
    w_days = int(st.session_state.working_days)
    p_per_day = int(st.session_state.periods_per_day)
    classes = [str(c).strip() for c in st.session_state.classes_list if str(c).strip()]
    df_allot = st.session_state.allotments_df

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][:w_days]
    teaching_periods = list(range(1, p_per_day + 1))
    slots_per_class = len(days) * len(teaching_periods)

    issues, _ = pre_check_allotments(df_allot, classes, slots_per_class)
    if issues:
        return {
            "status": "failed",
            "solver_status": "INPUT_VALIDATION_ERROR",
            "message": " | ".join(issues)
        }

    allotments_by_class = {}
    for c in classes:
        sub_df = df_allot[df_allot["Class"] == c]
        items = []
        for _, row in sub_df.iterrows():
            sub = str(row["Subject"]).strip()
            teacher = str(row["Teacher"]).strip()
            try: cnt = int(row["Periods/Week"])
            except: cnt = 4
            if sub and teacher and cnt > 0:
                items.append({"Subject": sub, "Teacher": teacher, "Count": cnt})

        req_total = sum(it["Count"] for it in items)
        if req_total < slots_per_class:
            diff = slots_per_class - req_total
            items.append({"Subject": "Library / Self Study", "Teacher": "Supervised Activity", "Count": diff})
        allotments_by_class[c] = items

    model = cp_model.CpModel()
    x = {}
    for c in classes:
        for d in days:
            for p in teaching_periods:
                for i in range(len(allotments_by_class[c])):
                    x[(c, d, p, i)] = model.NewBoolVar(f"x_{c}_{d}_{p}_{i}")

    # Constraint 1: One lesson per class per teaching period
    for c in classes:
        for d in days:
            for p in teaching_periods:
                model.AddExactlyOne(x[(c, d, p, i)] for i in range(len(allotments_by_class[c])))

    # Constraint 2: Satisfy exact weekly periods count
    for c in classes:
        for i, item in enumerate(allotments_by_class[c]):
            model.Add(sum(x[(c, d, p, i)] for d in days for p in teaching_periods) == item["Count"])

    # Constraint 3: Zero teacher double-booking
    all_teachers = set()
    for c in classes:
        for item in allotments_by_class[c]:
            if item["Teacher"] != "Supervised Activity":
                all_teachers.add(item["Teacher"])

    for d in days:
        for p in teaching_periods:
            for t in all_teachers:
                t_vars = [x[(c, d, p, i)] for c in classes for i, item in enumerate(allotments_by_class[c]) if item["Teacher"] == t]
                if len(t_vars) > 1:
                    model.AddAtMostOne(t_vars)

    # Constraint 4: Daily subject spread
    for c in classes:
        for d in days:
            for i, item in enumerate(allotments_by_class[c]):
                max_d = 1 if item["Count"] <= len(days) else (item["Count"] + len(days) - 1) // len(days)
                model.Add(sum(x[(c, d, p, i)] for p in teaching_periods) <= max_d)

    # Constraint 5: Avoid consecutive same subject
    for c in classes:
        for d in days:
            for i, item in enumerate(allotments_by_class[c]):
                for idx in range(len(teaching_periods) - 1):
                    p1 = teaching_periods[idx]
                    p2 = teaching_periods[idx + 1]
                    model.Add(x[(c, d, p1, i)] + x[(c, d, p2, i)] <= 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        full_schedule = {}
        for c in classes:
            for d in days:
                for p in teaching_periods:
                    for i, item in enumerate(allotments_by_class[c]):
                        if solver.Value(x[(c, d, p, i)]) == 1:
                            full_schedule[(c, d, p)] = (item["Subject"], item["Teacher"])
                            break
        return {
            "status": "success",
            "solver_status": solver.StatusName(status),
            "wall_time": round(solver.WallTime(), 3),
            "schedule": full_schedule,
            "classes": classes,
            "days": days,
            "periods": teaching_periods,
            "timeline": timeline,
            "dismissal_time": dismissal_time,
            "teachers": list(all_teachers)
        }
    else:
        return {
            "status": "failed",
            "solver_status": solver.StatusName(status),
            "message": "गणितीय रूप से यह कंस्ट्रेंट पूरा नहीं हो सकता। कृपया चेक करें कि किसी शिक्षक के पीरियड्स का योग उपलब्ध स्लॉट्स से अधिक तो नहीं है।"
        }

# ================= USER INTERFACE =================
st.title("🏫 School Timetable Pro (Fully Flexible Breaks & Timing)")
st.caption("Google OR-Tools CP-SAT सटीक शेड्यूलर + कस्टमाइज़ेबल बेल शेड्यूल (0, 1, 2, 3 या जितने चाहें उतने ब्रेक्स)")

tab_setup, tab_class_view, tab_teacher_view, tab_audit = st.tabs([
    "⚙️ 1. Setup & Bell Schedule", 
    "📅 2. Class-Wise Timetable", 
    "👨‍🏫 3. Teacher-Wise Schedule",
    "🔍 4. Conflict & Load Audit"
])

with tab_setup:
    st.subheader("1. Bell Schedule & Daily Timing Settings")
    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
    with col_t1:
        st.session_state.working_days = st.number_input("Working Days (सप्ताह में दिन)", 1, 7, int(st.session_state.working_days))
    with col_t2:
        st.session_state.periods_per_day = st.number_input("Teaching Periods per Day", 1, 15, int(st.session_state.periods_per_day))
    with col_t3:
        st.session_state.period_duration = st.number_input("Period Duration (मिनट में)", 15, 90, int(st.session_state.period_duration), step=5)
    with col_t4:
        st.session_state.school_start_time = st.time_input("School Start Time", value=st.session_state.school_start_time)

    st.markdown("---")
    st.subheader("☕ Custom Breaks & Recess Configuration")
    st.caption("आप अपनी इच्छानुसार जितने चाहें उतने ब्रेक्स (0, 1, 2, 3 आदि) रख सकते हैं। प्रत्येक ब्रेक का नाम, समय और पीरियड अपनी ज़रूरत के मुताबिक सेट करें:")

    max_possible_breaks = max(0, int(st.session_state.periods_per_day) - 1)
    
    col_ctrl1, col_ctrl2 = st.columns([2, 3])
    with col_ctrl1:
        selected_num_breaks = st.number_input(
            "दिन में कुल कितने Breaks / Recesses रखने हैं?", 
            min_value=0, 
            max_value=max_possible_breaks, 
            value=min(int(st.session_state.num_breaks), max_possible_breaks),
            step=1,
            help="अगर कोई ब्रेक नहीं चाहिए तो 0 चुनें, 1 ब्रेक के लिए 1, 2 के लिए 2, 3 के लिए 3 आदि।"
        )
        st.session_state.num_breaks = selected_num_breaks

    with col_ctrl2:
        st.write("**Quick Presets (जल्दी चुनने के लिए):**")
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        if p_col1.button("0 Break (कोई नहीं)", use_container_width=True):
            st.session_state.num_breaks = 0
            st.rerun()
        if p_col2.button("1 Break (Lunch)", use_container_width=True):
            st.session_state.num_breaks = 1
            st.rerun()
        if p_col3.button("2 Breaks (Recess+Lunch)", use_container_width=True):
            st.session_state.num_breaks = 2
            st.rerun()
        if p_col4.button("3 Breaks (Recess+Lunch+Snack)", use_container_width=True):
            st.session_state.num_breaks = 3
            st.rerun()

    active_breaks = []
    if st.session_state.num_breaks == 0:
        st.info("ℹ️ **कोई ब्रेक सेट नहीं है**: पूरे दिन लगातार टीचिंग पीरियड्स चलेंगे।")
    else:
        st.write(f"**नीचे {st.session_state.num_breaks} ब्रेक्स का विवरण सेट करें:**")
        default_break_presets = [
            {"name": "☕ Short Recess / Break 1", "after": 2, "duration": 15},
            {"name": "🍱 Lunch Break / Break 2", "after": 4, "duration": 35},
            {"name": "🥛 Afternoon Snack Break", "after": 6, "duration": 15},
            {"name": "🍎 Fruit Break", "after": 1, "duration": 10},
            {"name": "⚽ Evening Activity Break", "after": 7, "duration": 20},
        ]

        for i in range(1, int(st.session_state.num_breaks) + 1):
            with st.container():
                default_info = default_break_presets[i - 1] if i <= len(default_break_presets) else {"name": f"Break {i}", "after": min(i * 2, max_possible_breaks), "duration": 20}
                col_b1, col_b2, col_b3 = st.columns([3, 2, 2])
                with col_b1:
                    b_name = st.text_input(
                        f"Break {i} का नाम / लेबल:", 
                        value=default_info["name"], 
                        key=f"dyn_break_name_{i}"
                    )
                with col_b2:
                    b_after = st.number_input(
                        f"किस Period के बाद?", 
                        min_value=1, 
                        max_value=max_possible_breaks, 
                        value=min(default_info["after"], max_possible_breaks),
                        key=f"dyn_break_after_{i}"
                    )
                with col_b3:
                    b_dur = st.number_input(
                        f"Duration (मिनट में):", 
                        min_value=5, 
                        max_value=90, 
                        value=default_info["duration"], 
                        step=5,
                        key=f"dyn_break_dur_{i}"
                    )
                active_breaks.append({"name": b_name, "after_period": b_after, "duration": b_dur})

    # Timeline calculation
    current_timeline, current_dismissal = calculate_bell_schedule(
        st.session_state.school_start_time,
        st.session_state.period_duration,
        st.session_state.periods_per_day,
        active_breaks
    )

    with st.expander("🕒 Bell Schedule & Daily Timeline Preview (दिन की समय-सारणी देखें)", expanded=True):
        st.info(f"🔔 **School Start:** {st.session_state.school_start_time.strftime('%I:%M %p')} | 🏁 **School Dismissal:** {current_dismissal} | ⏱️ **Period Length:** {st.session_state.period_duration} मिनट | ☕ **Total Breaks:** {len(active_breaks)}")
        timeline_display = []
        for it in current_timeline:
            timeline_display.append({
                "Slot": it["label"],
                "Time Interval": it["time_str"],
                "Type": f"☕ Break / Recess" if it["type"] == "break" else "📚 Teaching Lecture"
            })
        st.dataframe(pd.DataFrame(timeline_display), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("2. Classes & Faculty Allotments")
    classes_input = st.text_input("Classes List (अल्पविराम से अलग करें):", value=", ".join(st.session_state.classes_list))
    st.session_state.classes_list = [c.strip() for c in classes_input.split(",") if c.strip()]

    # Excel / CSV Bulk Upload & Template Box
    with st.expander("📥 Bulk Upload from Excel / CSV (या Sample Template Download करें)", expanded=False):
        col_up1, col_up2 = st.columns([3, 1])
        with col_up1:
            uploaded_file = st.file_uploader(
                "Teacher & Subject Allotment File Upload (.xlsx, .xls, .csv):",
                type=["xlsx", "xls", "csv"],
                help="Columns: Class, Subject, Teacher, Periods/Week"
            )
        with col_up2:
            st.write("**Sample Template:**")
            sample_df = pd.DataFrame([
                {"Class": "6-A", "Subject": "Mathematics", "Teacher": "Nikum Sir", "Periods/Week": 6},
                {"Class": "6-A", "Subject": "Science", "Teacher": "Ashok Sir", "Periods/Week": 6},
                {"Class": "6-B", "Subject": "Mathematics", "Teacher": "Nikum Sir", "Periods/Week": 6},
                {"Class": "7-A", "Subject": "English", "Teacher": "Sandip Sir", "Periods/Week": 6},
            ])
            st.download_button(
                "📄 Download Template (CSV)",
                data=sample_df.to_csv(index=False).encode('utf-8'),
                file_name="timetable_template.csv",
                mime="text/csv",
                use_container_width=True
            )

        if uploaded_file is not None:
            try:
                raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
                clean_df = normalize_allotment_df(raw_df)
                if not clean_df.empty:
                    st.session_state.allotments_df = clean_df
                    extracted_classes = sorted(list(clean_df["Class"].unique()))
                    st.session_state.classes_list = extracted_classes
                    st.success(f"✅ फ़ाइल लोड हुई! कुल {len(clean_df)} अलॉटमेंट्स, {clean_df['Teacher'].nunique()} शिक्षक, और {len(extracted_classes)} क्लासेज़ सेट हो गईं।")
                    st.rerun()
                else:
                    st.error("फ़ाइल में कोई मान्य Class, Subject या Teacher डेटा नहीं मिला।")
            except Exception as e:
                st.error(f"फ़ाइल लोड करने में त्रुटि: {e}")

    # ================= LIVE HEALTH & PRE-CHECK DASHBOARD =================
    curr_df = st.session_state.allotments_df
    curr_classes = st.session_state.classes_list
    total_teachers = curr_df[curr_df["Teacher"] != "Supervised Activity"]["Teacher"].nunique()
    total_req_periods = curr_df["Periods/Week"].sum()
    slots_per_class = int(st.session_state.working_days) * int(st.session_state.periods_per_day)
    total_avail_slots = len(curr_classes) * slots_per_class

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1: st.metric("Active Classes", len(curr_classes))
    with col_m2: st.metric("Active Teachers", total_teachers)
    with col_m3: st.metric("Slots Demanded", f"{total_req_periods} / {total_avail_slots}")
    with col_m4: st.metric("Slots Capacity/Class", f"{slots_per_class} slots/week")

    issues, warnings = pre_check_allotments(curr_df, curr_classes, slots_per_class)
    if issues:
        for err in issues:
            st.error(f"⚠️ {err}")
    elif warnings:
        for w in warnings:
            st.warning(f"ℹ️ {w}")
    else:
        st.success("✅ **डेटा तैयार व संतुलित है:** किसी भी शिक्षक या क्लास में स्लॉट ओवरफ्लो नहीं है।")

    st.markdown("##### 📝 Allotment Table Editor (सीधे टेबल में भी एडिट कर सकते हैं):")
    st.session_state.allotments_df = st.data_editor(st.session_state.allotments_df, num_rows="dynamic", use_container_width=True)

    btn_disabled = bool(issues)
    if st.button("🚀 Generate Conflict-Free Timetable (Instant)", type="primary", use_container_width=True, disabled=btn_disabled):
        with st.spinner("Google OR-Tools CP-SAT मॉडल टाइमटेबल हल कर रहा है..."):
            res = solve_school_timetable(current_timeline, current_dismissal)
            if res["status"] == "success":
                st.session_state.generated_schedule = res
                st.success(f"🎉 टाइमटेबल तैयार! (समय: {res['wall_time']} सेकंड | स्थिति: {res['solver_status']})")
            else:
                st.error(f"❌ टाइमटेबल नहीं बन सका: {res['message']}")

with tab_class_view:
    if not st.session_state.generated_schedule:
        st.info("👈 कृपया पहले Tab 1 में जाकर 'Generate Conflict-Free Timetable' पर क्लिक करें।")
    else:
        sch = st.session_state.generated_schedule
        col_cv1, col_cv2 = st.columns([3, 1])
        with col_cv1:
            sel_class = st.selectbox("कक्षा चुनें:", sch["classes"])
        with col_cv2:
            master_excel_bytes = generate_master_excel(sch)
            st.download_button(
                "📊 Download Master Excel (सभी क्लासेज़)",
                data=master_excel_bytes,
                file_name="School_Master_Timetable.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        grid_data = []
        for d in sch["days"]:
            row = {"Day": d}
            for item in sch["timeline"]:
                h_name = item["header"]
                if item["type"] == "break":
                    row[h_name] = f"{item['label']}"
                else:
                    p = item["period_num"]
                    subj, teacher = sch["schedule"].get((sel_class, d, p), ("-", "-"))
                    row[h_name] = f"{subj}\n({teacher})"
            grid_data.append(row)
        df_class_grid = pd.DataFrame(grid_data)
        st.subheader(f"📋 Weekly Timetable: {sel_class}")
        st.dataframe(df_class_grid, use_container_width=True, hide_index=True)
        st.download_button(f"📥 Download {sel_class} Timetable (CSV)", df_class_grid.to_csv(index=False).encode('utf-8'), f"{sel_class}_timetable.csv", "text/csv")

with tab_teacher_view:
    if not st.session_state.generated_schedule:
        st.info("👈 कृपया पहले Tab 1 में जाकर 'Generate Conflict-Free Timetable' पर क्लिक करें।")
    else:
        sch = st.session_state.generated_schedule
        sel_teacher = st.selectbox("शिक्षक चुनें:", sorted(sch["teachers"]))
        teacher_grid = []
        total_load = 0
        for d in sch["days"]:
            row = {"Day": d}
            for item in sch["timeline"]:
                h_name = item["header"]
                if item["type"] == "break":
                    row[h_name] = f"{item['label']}"
                else:
                    p = item["period_num"]
                    found_c = None
                    found_s = None
                    for c in sch["classes"]:
                        s_name, t_name = sch["schedule"].get((c, d, p), ("-", "-"))
                        if t_name == sel_teacher:
                            found_c, found_s = c, s_name
                            break
                    if found_c:
                        row[h_name] = f"{found_s} ({found_c})"
                        total_load += 1
                    else:
                        row[h_name] = "Free"
            teacher_grid.append(row)
        df_teacher_grid = pd.DataFrame(teacher_grid)
        st.subheader(f"👨‍🏫 Weekly Schedule: {sel_teacher} (कुल पीरियड्स: {total_load})")
        st.dataframe(df_teacher_grid, use_container_width=True, hide_index=True)
        st.download_button(f"📥 Download {sel_teacher} Schedule (CSV)", df_teacher_grid.to_csv(index=False).encode('utf-8'), f"{sel_teacher}_roster.csv", "text/csv")

with tab_audit:
    if not st.session_state.generated_schedule:
        st.info("👈 कृपया पहले Tab 1 में जाकर 'Generate Conflict-Free Timetable' पर क्लिक करें।")
    else:
        sch = st.session_state.generated_schedule
        st.subheader("🔍 Mathematical Validation & Timing Audit")
        clashes = []
        for d in sch["days"]:
            for p in sch["periods"]:
                seen_t = {}
                for c in sch["classes"]:
                    s_name, t_name = sch["schedule"].get((c, d, p), ("-", "-"))
                    if t_name and t_name not in ["N/A", "Supervised Activity"]:
                        if t_name in seen_t: clashes.append(f"Clash on {d} Period {p}: {t_name} in {seen_t[t_name]} and {c}")
                        else: seen_t[t_name] = c

        if not clashes:
            st.success("✅ **Zero Clashes**: पूरा टाइमटेबल 100% क्लैश-फ्री है। कोई भी शिक्षक एक ही समय में दो जगह नहीं है।")
        else:
            for cl in clashes: st.error(cl)

        st.markdown("---")
        st.subheader("📊 Teacher Weekly Workload Summary")
        workload = []
        for t in sorted(sch["teachers"]):
            cnt = sum(1 for (c, d, p), (subj, t_assigned) in sch["schedule"].items() if t_assigned == t)
            workload.append({"Teacher Name": t, "Weekly Teaching Periods": cnt, "Daily Avg": round(cnt / len(sch["days"]), 2)})
        st.dataframe(pd.DataFrame(workload), use_container_width=True)

