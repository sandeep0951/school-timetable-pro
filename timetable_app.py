import streamlit as st
import pandas as pd
import datetime
import io
from ortools.sat.python import cp_model


st.set_page_config(page_title="School Timetable Pro (Deterministic & Conflict-Free)", layout="wide", page_icon="🏫")


# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 7
if "period_duration" not in st.session_state: st.session_state.period_duration = 40
if "school_start_time" not in st.session_state: st.session_state.school_start_time = datetime.time(8, 0)


if "num_breaks" not in st.session_state: st.session_state.num_breaks = 2


if "breaks_data" not in st.session_state:
    st.session_state.breaks_data = [
        {"name": "☕ Morning Recess", "after_period": 2, "duration": 15},
        {"name": "🍱 Lunch Break", "after_period": 4, "duration": 35},
        {"name": "🥛 Afternoon Snack Break", "after_period": 6, "duration": 15},
    ]


if "classes_list" not in st.session_state:
    st.session_state.classes_list = ["6-A", "6-B", "7-A", "7-B"]


if "allotments_df" not in st.session_state:
    sample_subs = [
        # Standard Academic Subjects
        ("Mathematics", 6, {"6-A": "Nikum Sir", "6-B": "Nikum Sir", "7-A": "Rahul Sir", "7-B": "Rahul Sir"}),
        ("Science", 5, {"6-A": "Ashok Sir", "6-B": "Ashok Sir", "7-A": "Kavita Mam", "7-B": "Kavita Mam"}),
        ("English", 6, {"6-A": "Sandip Sir", "6-B": "Usha Mam", "7-A": "Sandip Sir", "7-B": "Usha Mam"}),
        ("Hindi", 5, {"6-A": "Apeksha Mam", "6-B": "Apeksha Mam", "7-A": "Rajesh Sir", "7-B": "Rajesh Sir"}),
        ("Social Studies", 5, {"6-A": "Rudra Sir", "6-B": "Rudra Sir", "7-A": "Rakesh Sir", "7-B": "Rakesh Sir"}),
        ("Sanskrit", 4, {"6-A": "Padma Mam", "6-B": "Padma Mam", "7-A": "Padma Mam", "7-B": "Padma Mam"}),
        # Activity, Lab & Special Periods
        ("Computer Lab", 2, {"6-A": "Computer Lab", "6-B": "Computer Lab", "7-A": "Computer Lab", "7-B": "Computer Lab"}),
        ("Science Lab", 2, {"6-A": "Ashok Sir (Lab)", "6-B": "Ashok Sir (Lab)", "7-A": "Kavita Mam (Lab)", "7-B": "Kavita Mam (Lab)"}),
        ("Library", 2, {"6-A": "Librarian", "6-B": "Librarian", "7-A": "Librarian", "7-B": "Librarian"}),
        ("Sports / PE", 3, {"6-A": "Vikram Sir", "6-B": "Vikram Sir", "7-A": "Vikram Sir", "7-B": "Vikram Sir"}),
        ("Art & Craft", 2, {"6-A": "Meena Mam", "6-B": "Meena Mam", "7-A": "Meena Mam", "7-B": "Meena Mam"}),
    ]
    st.session_state.allotments_df = pd.DataFrame([
        {"Class": c, "Subject": sub, "Teacher": t_map[c], "Periods/Week": p}
        for sub, p, t_map in sample_subs for c in ["6-A", "6-B", "7-A", "7-B"]
    ])


if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = None


# ================= HELPER FUNCTIONS =================
def calculate_bell_schedule(start_time_obj, period_duration_mins, total_periods, breaks_list):
    """दैनिक समय सारिणी (Start Time, End Time) की पूरी टाइमलाइन की गणना करता है"""
    cur_time = datetime.datetime.combine(datetime.date.today(), start_time_obj)
    timeline = []
    
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
        elif any(k in c_clean for k in ["subject", "sub", "activity", "practical", "lab"]):
            col_map[col] = "Subject"
        elif any(k in c_clean for k in ["teacher", "faculty", "staff", "instructor", "incharge", "room"]):
            col_map[col] = "Teacher"
        elif any(k in c_clean for k in ["period", "count", "quota", "slot"]):
            col_map[col] = "Periods/Week"
    
    df = df.rename(columns=col_map)
    required = ["Class", "Subject", "Teacher", "Periods/Week"]
    for req in required:
        if req not in df.columns:
            if req == "Periods/Week": df[req] = 4
            elif req == "Teacher": df[req] = "Assigned Faculty"
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
    
    df_clean = df_allot.copy()
    df_clean["Periods/Week"] = pd.to_numeric(df_clean["Periods/Week"], errors="coerce").fillna(0).astype(int)
    
    for c in classes:
        sub_df = df_clean[df_clean["Class"] == c]
        total_req = int(sub_df["Periods/Week"].sum())
        if total_req > slots_per_class:
            issues.append(f"Class '{c}': कुल माँगे गए {total_req} पीरियड, जबकि उपलब्ध केवल {slots_per_class} स्लॉट्स हैं।")
    
    teacher_totals = df_clean[df_clean["Teacher"] != "Supervised Activity"].groupby("Teacher")["Periods/Week"].sum()
    for t, total_periods in teacher_totals.items():
        total_periods = int(total_periods)
        if total_periods > slots_per_class:
            issues.append(f"Teacher / Facility '{t}': कुल {total_periods} पीरियड असाइन हुए हैं, जो हफ़्ते की अधिकतम सीमा ({slots_per_class} स्लॉट्स) से ज़्यादा हैं।")
        elif total_periods >= int(slots_per_class * 0.9):
            warnings.append(f"Teacher / Facility '{t}': {total_periods}/{slots_per_class} स्लॉट्स (अत्यधिक लोड - {round(total_periods/slots_per_class*100)}%)")
            
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
        
        # Sheet 2: Teacher & Facility Workload Summary
        workload = []
        for t in sorted(sch["teachers"]):
            cnt = sum(1 for (c, d, p), (subj, t_assigned) in sch["schedule"].items() if t_assigned == t)
            workload.append({"Teacher / Facility Name": t, "Weekly Periods": cnt, "Daily Avg": round(cnt / len(sch["days"]), 2)})
        pd.DataFrame(workload).to_excel(writer, sheet_name="Teacher Workload", index=False)


    buf.seek(0)
    return buf.getvalue()


# ================= OR-TOOLS SOLVER ENGINE =================
def solve_school_timetable(timeline, dismissal_time, time_limit=15.0):
    w_days = int(st.session_state.working_days)
    p_per_day = int(st.session_state.periods_per_day)
    classes = [str(c).strip() for c in st.session_state.classes_list if str(c).strip()]
    df_allot = st.session_state.allotments_df.copy()
    df_allot["Periods/Week"] = pd.to_numeric(df_allot["Periods/Week"], errors="coerce").fillna(4).astype(int)


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


    # Constraint 3: Zero double-booking for teachers AND shared resources (Computer Lab, Library, Science Lab)
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
            "message": "गणितीय रूप से यह कंस्ट्रेंट पूरा नहीं हो सकता। कृपया चेक करें कि किसी शिक्षक या लैब के पीरियड्स का योग उपलब्ध स्लॉट्स से अधिक तो नहीं है।"
        }


# ================= USER INTERFACE =================
st.title("🏫 School Timetable Pro (Deterministic & Timing Engine)")
st.caption("Google OR-Tools CP-SAT सटीक शेड्यूलर + मल्टी-क्लास शिक्षक अलॉटमेंट, एक्सेल बल्क अपलोड और एक्टिविटी/लैब पीरियड्स")


tab_setup, tab_class_view, tab_teacher_view, tab_audit = st.tabs([
    "⚙️ 1. Setup & Allotments", 
    "📅 2. Class-Wise Timetable", 
    "👨‍🏫 3. Teacher & Lab Schedule",
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


    # Breaks Configuration
    max_possible_breaks = max(0, int(st.session_state.periods_per_day) - 1)
    with st.expander("☕ Breaks & Recess Settings (0, 1, 2, 3... जितने चाहें उतने ब्रेक्स सेट करें)", expanded=False):
        col_ctrl1, col_ctrl2 = st.columns([2, 3])
        with col_ctrl1:
            st.session_state.num_breaks = st.number_input(
                "दिन में कुल Breaks (0, 1, 2, 3...):", 
                min_value=0, 
                max_value=max_possible_breaks, 
                value=min(int(st.session_state.num_breaks), max_possible_breaks),
                step=1
            )
        with col_ctrl2:
            st.write("**Quick Presets:**")
            p_col1, p_col2, p_col3, p_col4 = st.columns(4)
            if p_col1.button("0 Break", use_container_width=True):
                st.session_state.num_breaks = 0
                st.rerun()
            if p_col2.button("1 (Lunch)", use_container_width=True):
                st.session_state.num_breaks = 1
                st.rerun()
            if p_col3.button("2 (Recess+Lunch)", use_container_width=True):
                st.session_state.num_breaks = 2
                st.rerun()
            if p_col4.button("3 Breaks", use_container_width=True):
                st.session_state.num_breaks = 3
                st.rerun()


        active_breaks = []
        default_break_presets = [
            {"name": "☕ Short Recess", "after": 2, "duration": 15},
            {"name": "🍱 Lunch Break", "after": 4, "duration": 35},
            {"name": "🥛 Afternoon Snack Break", "after": 6, "duration": 15},
            {"name": "🍎 Fruit Break", "after": 1, "duration": 10},
        ]
        if st.session_state.num_breaks > 0:
            for i in range(1, int(st.session_state.num_breaks) + 1):
                def_val = default_break_presets[i - 1] if i <= len(default_break_presets) else {"name": f"Break {i}", "after": min(i * 2, max_possible_breaks), "duration": 20}
                b_c1, b_c2, b_c3 = st.columns([3, 2, 2])
                with b_c1: b_name = st.text_input(f"Break {i} Name:", value=def_val["name"], key=f"b_name_inp_{i}")
                with b_c2: b_after = st.number_input(f"After Period:", 1, max_possible_breaks, min(def_val["after"], max_possible_breaks), key=f"b_aft_inp_{i}")
                with b_c3: b_dur = st.number_input(f"Duration (mins):", 5, 90, def_val["duration"], step=5, key=f"b_dur_inp_{i}")
                active_breaks.append({"name": b_name, "after_period": b_after, "duration": b_dur})


    current_timeline, current_dismissal = calculate_bell_schedule(
        st.session_state.school_start_time,
        st.session_state.period_duration,
        st.session_state.periods_per_day,
        active_breaks if st.session_state.num_breaks > 0 else []
    )


    with st.expander("🕒 Bell Schedule & Daily Timeline Preview", expanded=False):
        st.info(f"🔔 **School Start:** {st.session_state.school_start_time.strftime('%I:%M %p')} | 🏁 **School Dismissal:** {current_dismissal} | ⏱️ **Period Length:** {st.session_state.period_duration} मिनट | ☕ **Breaks:** {len(active_breaks)}")
        timeline_display = []
        for it in current_timeline:
            timeline_display.append({
                "Slot": it["label"],
                "Time Interval": it["time_str"],
                "Type": f"☕ Recess / Lunch" if it["type"] == "break" else "📚 Teaching Lecture"
            })
        st.dataframe(pd.DataFrame(timeline_display), use_container_width=True, hide_index=True)


    st.markdown("---")
    st.subheader("2. Faculty, Subjects & Activity Allotments")
    st.caption("आप चाहें तो एक क्लिक में पूरी एक्सेल/सीएसवी शीट अपलोड करें या नीचे दिए गए क्लास-वार फ़ॉर्म से मैन्युअल एंट्री करें:")


    slots_per_class = int(st.session_state.working_days) * int(st.session_state.periods_per_day)


    # ================= 2A: EXCEL / CSV BULK UPLOAD (ALWAYS AVAILABLE) =================
    with st.expander("📥 1. Bulk Upload from Excel / CSV (सभी शिक्षकों, विषयों व एक्टिविटीज़ का डेटा एक साथ अपलोड करें)", expanded=False):
        col_up1, col_up2 = st.columns([3, 1])
        with col_up1:
            uploaded_file = st.file_uploader(
                "Excel (.xlsx, .xls) या CSV फ़ाइल यहाँ ड्रैग करें या चुनें:",
                type=["xlsx", "xls", "csv"],
                help="कॉलम्स होने चाहिए: Class, Subject, Teacher, Periods/Week"
            )
        with col_up2:
            st.write("**सैंपल एक्सेल टेम्पलेट:**")
            sample_df = pd.DataFrame([
                {"Class": "6-A", "Subject": "Mathematics", "Teacher": "Nikum Sir", "Periods/Week": 6},
                {"Class": "6-A", "Subject": "Science", "Teacher": "Ashok Sir", "Periods/Week": 5},
                {"Class": "6-A", "Subject": "Science Lab", "Teacher": "Ashok Sir (Lab)", "Periods/Week": 2},
                {"Class": "6-A", "Subject": "Computer Lab", "Teacher": "Computer Lab", "Periods/Week": 2},
                {"Class": "6-A", "Subject": "Library", "Teacher": "Librarian", "Periods/Week": 2},
                {"Class": "6-A", "Subject": "Sports / PE", "Teacher": "Vikram Sir", "Periods/Week": 3},
                {"Class": "6-B", "Subject": "Mathematics", "Teacher": "Nikum Sir", "Periods/Week": 6},
                {"Class": "7-A", "Subject": "English", "Teacher": "Sandip Sir", "Periods/Week": 6},
            ])
            st.download_button(
                "📄 Download Sample Template",
                data=sample_df.to_csv(index=False).encode('utf-8'),
                file_name="school_timetable_allotments_template.csv",
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
                    st.success(f"✅ फ़ाइल सफलतापूर्वक अपलोड हुई! कुल {len(clean_df)} अलॉटमेंट्स, {clean_df['Teacher'].nunique()} शिक्षक/लैब्स, और {len(extracted_classes)} क्लासेज़ लोड हो गईं।")
                    st.rerun()
                else:
                    st.error("फ़ाइल में कोई मान्य Class, Subject या Teacher डेटा नहीं मिला।")
            except Exception as e:
                st.error(f"फ़ाइल लोड करने में त्रुटि: {e}")


    # ================= 2B: SCHOOL CLASSES & SECTIONS SETUP (NURSERY TO 12TH WIZARD) =================
    st.markdown("#### 🏫 2. School Classes & Sections Setup (Nursery से 12th तक कक्षाएँ व सेक्शंस जोड़ें)")
    st.caption("💡 **Step 1:** पहले चुनें कि स्कूल में कौन-कौन सी क्लासेस हैं (Nursery से 12 तक) | **Step 2:** फिर प्रत्येक क्लास के सामने Dropdown से कुल Sections (A, B, C...) चुनें:")

    STANDARD_CLASSES = ["Nursery", "LKG", "UKG", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
    SECTION_OPTIONS = [
        "1 Section (A)", 
        "2 Sections (A, B)", 
        "3 Sections (A, B, C)", 
        "4 Sections (A, B, C, D)", 
        "5 Sections (A, B, C, D, E)", 
        "6 Sections (A, B, C, D, E, F)",
        "No Section (Only Class Name)"
    ]
    SECTION_LETTER_MAP = {
        "1 Section (A)": ["A"],
        "2 Sections (A, B)": ["A", "B"],
        "3 Sections (A, B, C)": ["A", "B", "C"],
        "4 Sections (A, B, C, D)": ["A", "B", "C", "D"],
        "5 Sections (A, B, C, D, E)": ["A", "B", "C", "D", "E"],
        "6 Sections (A, B, C, D, E, F)": ["A", "B", "C", "D", "E", "F"],
        "No Section (Only Class Name)": [""]
    }

    with st.expander("⚙️ Class & Section Setup Wizard (Nursery से 12th तक क्लासेज व सेक्शंस एक साथ सेट करें)", expanded=True):
        st.write("**त्वरित प्रीसेट (Quick Presets):**")
        p_c1, p_c2, p_c3, p_c4, p_c5 = st.columns(5)
        if p_c1.button("🏫 Full (Nursery-12)", use_container_width=True):
            st.session_state.selected_school_grades = STANDARD_CLASSES[:]
            st.rerun()
        if p_c2.button("🎒 Primary (1st-5th)", use_container_width=True):
            st.session_state.selected_school_grades = ["1", "2", "3", "4", "5"]
            st.rerun()
        if p_c3.button("📘 Middle (6th-8th)", use_container_width=True):
            st.session_state.selected_school_grades = ["6", "7", "8"]
            st.rerun()
        if p_c4.button("🎓 Secondary (9th-12th)", use_container_width=True):
            st.session_state.selected_school_grades = ["9", "10", "11", "12"]
            st.rerun()
        if p_c5.button("⭐ Default (6 & 7)", use_container_width=True):
            st.session_state.selected_school_grades = ["6", "7"]
            st.rerun()

        if "selected_school_grades" not in st.session_state:
            init_grades = set()
            for c in st.session_state.classes_list:
                base_g = c.split("-")[0].strip()
                if base_g in STANDARD_CLASSES:
                    init_grades.add(base_g)
            st.session_state.selected_school_grades = sorted(list(init_grades), key=lambda x: STANDARD_CLASSES.index(x) if x in STANDARD_CLASSES else 99) or ["6", "7"]

        chosen_grades = st.multiselect(
            "1. स्कूल में कौन-कौन सी Classes हैं चुनें (Nursery से 12 तक):",
            options=STANDARD_CLASSES,
            default=[g for g in st.session_state.selected_school_grades if g in STANDARD_CLASSES],
            help="यहाँ अपनी स्कूल की सभी कक्षाएँ सेलेक्ट करें। सेलेक्ट करते ही नीचे प्रत्येक क्लास के सेक्शंस चुनने का विकल्प आ जाएगा।"
        )
        st.session_state.selected_school_grades = chosen_grades

        if chosen_grades:
            st.write("**2. प्रत्येक चुनी गई Class के आगे Sections (A से आगे तक) Dropdown से चुनें:**")
            
            # Quick apply sections across all chosen classes
            q_col1, q_col2 = st.columns([3, 2])
            with q_col1:
                quick_sec_all = st.selectbox(
                    "⚡ सभी चुनी गई Classes के लिए एक साथ Sections सेट करें (Quick Apply):",
                    [
                        "-- प्रत्येक क्लास का अलग-अलग सेट करें --",
                        "1 Section (A)",
                        "2 Sections (A, B)",
                        "3 Sections (A, B, C)",
                        "4 Sections (A, B, C, D)",
                        "5 Sections (A, B, C, D, E)",
                        "6 Sections (A, B, C, D, E, F)"
                    ]
                )
            with q_col2:
                st.write("")
                st.write("")
                if quick_sec_all != "-- प्रत्येक क्लास का अलग-अलग सेट करें --" and st.button("⚡ Apply to All Selected Classes", use_container_width=True):
                    for g in chosen_grades:
                        st.session_state[f"sec_sel_{g}"] = quick_sec_all
                    st.success(f"सभी क्लासेस के लिए '{quick_sec_all}' सेट हो गया!")
                    st.rerun()

            # Grid of per-class dropdowns
            g_cols = st.columns(3)
            for idx, grade in enumerate(chosen_grades):
                with g_cols[idx % 3]:
                    default_val = st.session_state.get(
                        f"sec_sel_{grade}", 
                        "1 Section (A)" if grade in ["Nursery", "LKG", "UKG"] else "2 Sections (A, B)"
                    )
                    val_idx = SECTION_OPTIONS.index(default_val) if default_val in SECTION_OPTIONS else 1
                    st.selectbox(
                        f"📌 Class **{grade}** Sections:",
                        options=SECTION_OPTIONS,
                        index=val_idx,
                        key=f"sec_sel_{grade}"
                    )

            # Generate list of classes
            generated_classes = []
            for g in chosen_grades:
                sec_choice = st.session_state.get(f"sec_sel_{g}", "1 Section (A)" if g in ["Nursery", "LKG", "UKG"] else "2 Sections (A, B)")
                letters = SECTION_LETTER_MAP.get(sec_choice, ["A", "B"])
                for l in letters:
                    if l:
                        generated_classes.append(f"{g}-{l}")
                    else:
                        generated_classes.append(g)

            st.info(f"📋 **तैयार होने वाली कुल {len(generated_classes)} Classes & Sections:** ")
            
            col_save1, col_save2 = st.columns([3, 1])
            with col_save1:
                st.caption("बटन दबाते ही यह सभी क्लासेज व सेक्शंस आपके टाइमटेबल और टेबल के ड्रॉपडाउन में सेव हो जाएंगे।")
            with col_save2:
                if st.button("💾 Save & Update Classes", type="primary", use_container_width=True):
                    if generated_classes:
                        st.session_state.classes_list = generated_classes
                        st.success(f"✅ कुल {len(generated_classes)} क्लासेस व सेक्शंस अपडेट हो गए!")
                        st.rerun()

        # Option to add custom class if any
        with st.expander("➕ कोई अतिरिक्त कस्टम क्लास जोड़ें (उदा. 11-Science, 12-Arts)", expanded=False):
            c_add1, c_add2 = st.columns([3, 1])
            with c_add1:
                custom_cls = st.text_input("कस्टम क्लास का नाम:", placeholder="उदा. 11-Science")
            with c_add2:
                st.write("")
                st.write("")
                if st.button("➕ Add Custom", use_container_width=True):
                    cc_clean = custom_cls.strip()
                    if cc_clean and cc_clean not in st.session_state.classes_list:
                        st.session_state.classes_list.append(cc_clean)
                        st.success(f"Class '{cc_clean}' जोड़ी गई!")
                        st.rerun()

    # Active Class Selector & Delete
    col_c_sel, col_c_del = st.columns([4, 1])
    with col_c_sel:
        if not st.session_state.classes_list:
            st.session_state.classes_list = ["6-A"]
        sel_entry_class = st.selectbox(
            "वर्तमान में किस Class / Section का डेटा देखना या जोड़ना है चुनें:", 
            st.session_state.classes_list
        )
    with col_c_del:
        st.write("")
        st.write("")
        if st.button("🗑️ Delete This Class", type="secondary", use_container_width=True):
            if len(st.session_state.classes_list) > 1:
                st.session_state.classes_list.remove(sel_entry_class)
                st.session_state.allotments_df = st.session_state.allotments_df[st.session_state.allotments_df["Class"] != sel_entry_class]
                st.warning(f"Class '{sel_entry_class}' हटा दी गई!")
                st.rerun()
            else:
                st.error("कम से कम एक Class होनी आवश्यक है!")


    # Class Load Status Indicator (SAFE NUMERIC PARSING)
    class_current_rows = st.session_state.allotments_df[st.session_state.allotments_df["Class"] == sel_entry_class].copy()
    if not class_current_rows.empty:
        cls_allotted_periods = int(pd.to_numeric(class_current_rows["Periods/Week"], errors="coerce").fillna(0).sum())
    else:
        cls_allotted_periods = 0


    col_stat1, col_stat2 = st.columns([3, 2])
    with col_stat1:
        st.write(f"**{sel_entry_class} का कुल लोड:** `{cls_allotted_periods} / {slots_per_class}` पीरियड्स प्रति सप्ताह")
        progress_val = min(1.0, max(0.0, float(cls_allotted_periods) / float(slots_per_class))) if slots_per_class > 0 else 0.0
        st.progress(progress_val)
    with col_stat2:
        if cls_allotted_periods == slots_per_class:
            st.success(f"✅ एकदम सही: {slots_per_class} स्लॉट्स पूरे हैं।")
        elif cls_allotted_periods < slots_per_class:
            st.info(f"ℹ️ {slots_per_class - cls_allotted_periods} स्लॉट्स खाली हैं (बाकी में लाइब्रेरी / सेल्फ-स्टडी आ जाएगी)।")
        else:
            st.error(f"⚠️ ओवरफ्लो: {cls_allotted_periods - slots_per_class} पीरियड कम करने होंगे।")


    # Quick Activity Presets Bar
    st.write(f"**{sel_entry_class} में विषय या स्पेशल एक्टिविटी / लैब पीरियड जोड़ें:**")
    st.caption("💡 नीचे दिए गए किसी भी बटन पर क्लिक करके सीधे कॉमन एक्टिविटी जोड़ें या नीचे दिए गए फ़ॉर्म से मल्टी-क्लास असाइन करें:")
    
    act_c1, act_c2, act_c3, act_c4, act_c5, act_c6 = st.columns(6)
    preset_choice = None
    if act_c1.button("🧪 Science Lab", use_container_width=True): preset_choice = ("Science Lab", "Science Lab / Instructor", 2)
    if act_c2.button("💻 Computer Lab", use_container_width=True): preset_choice = ("Computer Lab", "Computer Lab", 2)
    if act_c3.button("📚 Library", use_container_width=True): preset_choice = ("Library", "Librarian", 2)
    if act_c4.button("⚽ Sports / PE", use_container_width=True): preset_choice = ("Sports / PE", "Sports Coach", 3)
    if act_c5.button("🎨 Art & Craft", use_container_width=True): preset_choice = ("Art & Craft", "Art Teacher", 2)
    if act_c6.button("🎵 Music / Dance", use_container_width=True): preset_choice = ("Music / Dance", "Music Teacher", 2)


    if preset_choice:
        p_sub, p_tea, p_cnt = preset_choice
        new_row = pd.DataFrame([{"Class": sel_entry_class, "Subject": p_sub, "Teacher": p_tea, "Periods/Week": p_cnt}])
        st.session_state.allotments_df = pd.concat([st.session_state.allotments_df, new_row], ignore_index=True)
        st.success(f"✅ {sel_entry_class} में '{p_sub} ({p_tea})' जोड़ दिया गया!")
        st.rerun()


    # Manual Add Form with Multi-Class & Section Selection
    with st.form(f"manual_add_form_{sel_entry_class}", clear_on_submit=False):
        col_f1, col_f2 = st.columns([1, 1])
        with col_f1:
            in_subj = st.text_input("Subject / Activity का नाम:", placeholder="उदा. Mathematics, Science Lab, Yoga...")
        with col_f2:
            in_teacher = st.text_input("Teacher / Lab / In-charge का नाम:", placeholder="उदा. Nikum Sir, Sharma Sir, Computer Lab...")


        # Class / Sections Selection right before Periods/Week
        col_f3, col_f4, col_f5 = st.columns([2.5, 1.2, 1.3])
        with col_f3:
            in_classes = st.multiselect(
                "Class & Sections (एक साथ कई क्लासेस चुन सकते हैं, जैसे 8-A और 7-B):",
                options=st.session_state.classes_list,
                default=[sel_entry_class] if sel_entry_class in st.session_state.classes_list else [],
                help="अगर शिक्षक एक से अधिक क्लासेज में पढ़ाते हैं तो उन सभी को यहाँ सेलेक्ट करें।"
            )
        with col_f4:
            in_periods = st.number_input("Periods / Week:", 1, slots_per_class, 6)
        with col_f5:
            st.write("")
            st.write("")
            submit_add = st.form_submit_button("➕ Allot Subject", use_container_width=True, type="primary")


        if submit_add:
            s_c = in_subj.strip()
            t_c = in_teacher.strip()
            target_cls_list = in_classes if in_classes else [sel_entry_class]
            if s_c and t_c and target_cls_list:
                new_entries = []
                for c_target in target_cls_list:
                    if c_target not in st.session_state.classes_list:
                        st.session_state.classes_list.append(c_target)
                    new_entries.append({
                        "Class": c_target,
                        "Subject": s_c,
                        "Teacher": t_c,
                        "Periods/Week": int(in_periods)
                    })
                st.session_state.allotments_df = pd.concat([st.session_state.allotments_df, pd.DataFrame(new_entries)], ignore_index=True)
                st.success(f"✅ '{s_c} ({t_c})' को {', '.join(target_cls_list)} में प्रति सप्ताह {in_periods} पीरियड्स के साथ जोड़ दिया गया!")
                st.rerun()
            else:
                st.error("कृपया Subject, Teacher और कम से कम एक Class अवश्य चुनें!")


    # Multi-select dropdown column configuration for 'Class & Section' (between Teacher and Periods/Week)
    avail_classes = [str(c).strip() for c in st.session_state.classes_list if str(c).strip()]
    if not avail_classes:
        avail_classes = ["6-A"]

    class_col_cfg = None
    if hasattr(st.column_config, "MultiselectColumn"):
        class_col_cfg = st.column_config.MultiselectColumn(
            "Class & Section",
            help="ड्रॉपडाउन से एक या अधिक Classes & Sections चुनें (उदा. 6-A, 6-B, 7-A)",
            options=avail_classes,
            default=[sel_entry_class] if sel_entry_class in avail_classes else [avail_classes[0]],
            required=True,
            width="medium"
        )
    elif hasattr(st.column_config, "SelectboxColumn"):
        class_col_cfg = st.column_config.SelectboxColumn(
            "Class & Section",
            help="ड्रॉपडाउन से Class चुनें",
            options=avail_classes,
            required=True,
            width="medium"
        )
    else:
        class_col_cfg = st.column_config.TextColumn(
            "Class & Section",
            help="Classes (कॉमा लगाकर लिखें, जैसे 6-A, 6-B)",
            width="medium"
        )

    editor_col_config = {
        "Subject": st.column_config.TextColumn("Subject", required=True, width="medium"),
        "Teacher": st.column_config.TextColumn("Teacher", required=True, width="medium"),
        "Class & Section": class_col_cfg,
        "Periods/Week": st.column_config.NumberColumn("Periods/Week", min_value=1, max_value=slots_per_class, step=1, required=True, width="small")
    }

    # View Allotments Tabs (Class-Wise vs Teacher-Wise vs All-Classes)
    tab_view_cls, tab_view_tch, tab_view_all = st.tabs([
        f"🏫 {sel_entry_class} की विषय सूची (Multi-Class Table)",
        "👨‍🏫 Teacher-Wise Roster (शिक्षक-वार सूची)",
        "📋 All Classes Consolidated Table (सभी कक्षाओं की संयुक्त टेबल)"
    ])


    with tab_view_cls:
        st.write(f"##### 📝 {sel_entry_class} के अलॉटमेंट्स (टेबल में सीधे 'Class' कॉलम में एक साथ कई क्लासेस चुन सकते हैं):")
        
        # Build table with Subject | Teacher | Class & Section (multiple) | Periods/Week
        table_rows = []
        for _, r in class_current_rows.iterrows():
            sub = str(r["Subject"]).strip()
            tea = str(r["Teacher"]).strip()
            try:
                pw = int(pd.to_numeric(r["Periods/Week"], errors="coerce"))
                if pw <= 0: pw = 4
            except:
                pw = 4
            
            # Find all classes that share this exact Subject, Teacher, and Periods/Week
            matched_cls = st.session_state.allotments_df[
                (st.session_state.allotments_df["Subject"] == sub) & 
                (st.session_state.allotments_df["Teacher"] == tea) & 
                (st.session_state.allotments_df["Periods/Week"] == pw)
            ]["Class"].unique().tolist()
            
            if sel_entry_class not in matched_cls:
                matched_cls.append(sel_entry_class)
            
            matched_cls = sorted(list(set(matched_cls)))
            table_rows.append({
                "Subject": sub,
                "Teacher": tea,
                "Class & Section": matched_cls,
                "Periods/Week": pw
            })
            
        class_table = pd.DataFrame(table_rows)
        if class_table.empty:
            class_table = pd.DataFrame(columns=["Subject", "Teacher", "Class & Section", "Periods/Week"])
        else:
            class_table = class_table[["Subject", "Teacher", "Class & Section", "Periods/Week"]]

        edited_class_table = st.data_editor(
            class_table, 
            column_config=editor_col_config,
            num_rows="dynamic", 
            use_container_width=True, 
            key=f"class_editor_{sel_entry_class}"
        )

        if not edited_class_table.equals(class_table):
            # 1. Track which (Class, Subject, Teacher) tuples were originally displayed
            old_tuples = set()
            for _, r in class_table.iterrows():
                s = str(r["Subject"]).strip()
                t = str(r["Teacher"]).strip()
                c_val = r.get("Class & Section", r.get("Class", []))
                c_list = c_val if isinstance(c_val, (list, tuple, set)) else [x.strip() for x in str(c_val).replace(";", ",").split(",") if x.strip()]
                for c in c_list:
                    old_tuples.add((c, s, t))

            # 2. Parse edited rows
            new_rows = []
            classes_to_clean = set()
            for _, r in edited_class_table.iterrows():
                s = str(r.get("Subject", "")).strip()
                t = str(r.get("Teacher", "")).strip()
                if not s or not t or pd.isna(s) or pd.isna(t) or s.lower() in ["nan", "none", ""] or t.lower() in ["nan", "none", ""]:
                    continue
                
                try:
                    pw = int(pd.to_numeric(r.get("Periods/Week", 4), errors="coerce"))
                    if pw <= 0: pw = 4
                except:
                    pw = 4
                
                c_val = r.get("Class & Section", r.get("Class", [sel_entry_class]))
                if isinstance(c_val, (list, tuple, set)):
                    c_list = [str(x).strip() for x in c_val if str(x).strip()]
                elif isinstance(c_val, str):
                    c_list = [x.strip() for x in c_val.replace(";", ",").split(",") if x.strip()]
                elif pd.isna(c_val) or c_val is None:
                    c_list = []
                else:
                    c_list = [str(c_val).strip()]
                
                if not c_list:
                    c_list = [sel_entry_class]
                
                for c in c_list:
                    if c:
                        if c not in st.session_state.classes_list:
                            st.session_state.classes_list.append(c)
                        new_rows.append({"Class": c, "Subject": s, "Teacher": t, "Periods/Week": pw})
                        classes_to_clean.add((c, s))

            def should_keep(row):
                tup = (row["Class"], row["Subject"], row["Teacher"])
                if tup in old_tuples:
                    return False
                if (row["Class"], row["Subject"]) in classes_to_clean:
                    return False
                return True

            kept_df = st.session_state.allotments_df[st.session_state.allotments_df.apply(should_keep, axis=1)]
            st.session_state.allotments_df = pd.concat([kept_df, pd.DataFrame(new_rows)], ignore_index=True)
            st.rerun()


    with tab_view_tch:
        active_teachers_list = sorted([t for t in st.session_state.allotments_df["Teacher"].dropna().unique() if t != "Supervised Activity"])
        if active_teachers_list:
            sel_view_teacher = st.selectbox("शिक्षक चुनें:", active_teachers_list)
            t_rows = st.session_state.allotments_df[st.session_state.allotments_df["Teacher"] == sel_view_teacher]
            t_total_periods = int(pd.to_numeric(t_rows["Periods/Week"], errors="coerce").fillna(0).sum())
            st.write(f"**{sel_view_teacher} का कुल वर्कलोड:** `{t_total_periods} / {slots_per_class}` पीरियड्स प्रति सप्ताह")
            
            t_display = t_rows[["Class", "Subject", "Periods/Week"]].reset_index(drop=True)
            edited_t_table = st.data_editor(t_display, num_rows="dynamic", use_container_width=True, key=f"t_editor_{sel_view_teacher}")
            if not edited_t_table.equals(t_display):
                cleaned_t = edited_t_table.dropna(subset=["Class", "Subject"]).copy()
                cleaned_t["Teacher"] = sel_view_teacher
                cleaned_t["Periods/Week"] = pd.to_numeric(cleaned_t["Periods/Week"], errors="coerce").fillna(4).astype(int).clip(lower=1)
                other_t_rows = st.session_state.allotments_df[st.session_state.allotments_df["Teacher"] != sel_view_teacher]
                st.session_state.allotments_df = pd.concat([other_t_rows, cleaned_t[["Class", "Subject", "Teacher", "Periods/Week"]]], ignore_index=True)
                st.rerun()
        else:
            st.info("अभी कोई शिक्षक नहीं जुड़े हैं।")

    with tab_view_all:
        st.write("##### 📋 स्कूल के सभी विषय व शिक्षकों की संयुक्त सूची (सीधे 'Class' कॉलम में मल्टीपल क्लासेस जोड़ें/हटाएं):")
        all_table_rows = []
        if not st.session_state.allotments_df.empty:
            for (sub, tea, pw), grp in st.session_state.allotments_df.groupby(["Subject", "Teacher", "Periods/Week"], as_index=False):
                all_table_rows.append({
                    "Subject": sub,
                    "Teacher": tea,
                    "Class & Section": sorted(list(grp["Class"].unique())),
                    "Periods/Week": int(pw)
                })
        master_multi_df = pd.DataFrame(all_table_rows)
        if master_multi_df.empty:
            master_multi_df = pd.DataFrame(columns=["Subject", "Teacher", "Class & Section", "Periods/Week"])
        else:
            master_multi_df = master_multi_df[["Subject", "Teacher", "Class & Section", "Periods/Week"]]
            
        edited_master_table = st.data_editor(
            master_multi_df,
            column_config=editor_col_config,
            num_rows="dynamic",
            use_container_width=True,
            key="master_multi_editor"
        )

        if not edited_master_table.equals(master_multi_df):
            new_m_rows = []
            for _, r in edited_master_table.iterrows():
                s = str(r.get("Subject", "")).strip()
                t = str(r.get("Teacher", "")).strip()
                if not s or not t or s.lower() in ["nan", "none", ""] or t.lower() in ["nan", "none", ""]:
                    continue
                try:
                    pw = int(pd.to_numeric(r.get("Periods/Week", 4), errors="coerce").fillna(4))
                    if pw <= 0: pw = 4
                except:
                    pw = 4
                c_val = r.get("Class & Section", r.get("Class", []))
                if isinstance(c_val, (list, tuple, set)):
                    c_list = [str(x).strip() for x in c_val if str(x).strip()]
                elif isinstance(c_val, str):
                    c_list = [x.strip() for x in c_val.replace(";", ",").split(",") if x.strip()]
                else:
                    c_list = []
                for c in c_list:
                    if c:
                        if c not in st.session_state.classes_list:
                            st.session_state.classes_list.append(c)
                        new_m_rows.append({"Class": c, "Subject": s, "Teacher": t, "Periods/Week": pw})
            if new_m_rows:
                st.session_state.allotments_df = pd.DataFrame(new_m_rows)
                st.rerun()


    # Clone / Copy Section Tool
    other_classes = [c for c in st.session_state.classes_list if c != sel_entry_class]
    if other_classes:
        with st.expander(f"📋 {sel_entry_class} के सभी विषय व एक्टिविटीज़ किसी अन्य सेक्शन में कॉपी करें (Quick Replicate)"):
            col_cp1, col_cp2 = st.columns([3, 2])
            with col_cp1:
                target_cls = st.selectbox(f"किस सेक्शन में कॉपी करना है?", other_classes)
            with col_cp2:
                st.write("")
                st.write("")
                if st.button(f"Copy All to {target_cls}", use_container_width=True):
                    src_rows = st.session_state.allotments_df[st.session_state.allotments_df["Class"] == sel_entry_class].copy()
                    src_rows["Class"] = target_cls
                    other_than_target = st.session_state.allotments_df[st.session_state.allotments_df["Class"] != target_cls]
                    st.session_state.allotments_df = pd.concat([other_than_target, src_rows], ignore_index=True)
                    st.success(f"✅ {sel_entry_class} के सारे विषय व एक्टिविटीज़ '{target_cls}' में कॉपी हो गए!")
                    st.rerun()


    # ================= 2C: FULL MASTER ALLOTMENTS TABLE (EXPANDABLE) =================
    with st.expander("📋 3. View / Edit Full Master Table (सभी क्लासेस और टीचर्स की संयुक्त टेबल)", expanded=False):
        st.caption("यहाँ सभी क्लासेस, विषयों और एक्टिविटीज़ का पूरा डेटा एक साथ एडिट किया जा सकता है:")
        st.session_state.allotments_df = st.data_editor(st.session_state.allotments_df, num_rows="dynamic", use_container_width=True)
        st.session_state.allotments_df["Periods/Week"] = pd.to_numeric(st.session_state.allotments_df["Periods/Week"], errors="coerce").fillna(4).astype(int).clip(lower=1)


    # ================= LIVE HEALTH & CAPACITY AUDIT =================
    st.markdown("---")
    st.subheader("3. Live System Health & Capacity Audit")


    curr_df = st.session_state.allotments_df.copy()
    curr_df["Periods/Week"] = pd.to_numeric(curr_df["Periods/Week"], errors="coerce").fillna(4).astype(int)
    curr_classes = st.session_state.classes_list
    total_teachers = curr_df[curr_df["Teacher"] != "Supervised Activity"]["Teacher"].nunique()
    total_req_periods = int(curr_df["Periods/Week"].sum())
    total_avail_slots = len(curr_classes) * slots_per_class


    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1: st.metric("Active Classes", len(curr_classes))
    with col_m2: st.metric("Active Teachers & Labs", total_teachers)
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
        st.success("✅ **डेटा तैयार व संतुलित है:** किसी भी शिक्षक, लैब या क्लास में स्लॉट ओवरफ्लो नहीं है।")


    btn_disabled = bool(issues) or len(curr_classes) == 0
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
        sel_teacher = st.selectbox("शिक्षक या लैब/फैसिलिटी चुनें:", sorted(sch["teachers"]))
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
            st.success("✅ **Zero Clashes**: पूरा टाइमटेबल 100% क्लैश-फ्री है। कोई भी शिक्षक या लैब एक ही समय में दो जगह नहीं है।")
        else:
            for cl in clashes: st.error(cl)


        st.markdown("---")
        st.subheader("📊 Teacher & Facility Weekly Workload Summary")
        workload = []
        for t in sorted(sch["teachers"]):
            cnt = sum(1 for (c, d, p), (subj, t_assigned) in sch["schedule"].items() if t_assigned == t)
            workload.append({"Teacher / Facility Name": t, "Weekly Teaching Periods": cnt, "Daily Avg": round(cnt / len(sch["days"]), 2)})
        st.dataframe(pd.DataFrame(workload), use_container_width=True)
