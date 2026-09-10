import streamlit as st
import pandas as pd
import io
from ortools.sat.python import cp_model

st.set_page_config(page_title="School Timetable Pro (Deterministic & Conflict-Free)", layout="wide", page_icon="🏫")

# ================= STATE INITIALIZATION =================
if "working_days" not in st.session_state: st.session_state.working_days = 6
if "periods_per_day" not in st.session_state: st.session_state.periods_per_day = 7
if "break_at" not in st.session_state: st.session_state.break_at = 4

if "classes_list" not in st.session_state:
    st.session_state.classes_list = ["6-A", "6-B", "7-A", "7-B"]

if "allotments_df" not in st.session_state:
    sample_subs = [
        ("Mathematics", 6, {"6-A": "Nikum Sir", "6-B": "Nikum Sir", "7-A": "Rahul Sir", "7-B": "Rahul Sir"}),
        ("Science", 6, {"6-A": "Ashok Sir", "6-B": "Ashok Sir", "7-A": "Kavita Mam", "7-B": "Kavita Mam"}),
        ("English", 6, {"6-A": "Sandip Sir", "6-B": "Usha Mam", "7-A": "Sandip Sir", "7-B": "Usha Mam"}),
        ("Hindi", 6, {"6-A": "Apeksha Mam", "6-B": "Apeksha Mam", "7-A": "Rajesh Sir", "7-B": "Rajesh Sir"}),
        ("Social Studies", 5, {"6-A": "Rudra Sir", "6-B": "Rudra Sir", "7-A": "Rakesh Sir", "7-B": "Rakesh Sir"}),
        ("Sanskrit", 4, {"6-A": "Padma Mam", "6-B": "Padma Mam", "7-A": "Padma Mam", "7-B": "Padma Mam"}),
        ("Sports", 3, {"6-A": "Vikram Sir", "6-B": "Vikram Sir", "7-A": "Vikram Sir", "7-B": "Vikram Sir"}),
    ]
    st.session_state.allotments_df = pd.DataFrame([
        {"Class": c, "Subject": sub, "Teacher": t_map[c], "Periods/Week": p}
        for sub, p, t_map in sample_subs for c in ["6-A", "6-B", "7-A", "7-B"]
    ])

if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = None

# ================= HELPER FUNCTIONS =================
def normalize_allotment_df(df):
    """Excel / CSV कॉलम्स को पहचानकर स्टैंडर्ड स्कीमा में बदलता है और गलत डेटा साफ करता है"""
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
            
    # सख्त स्पेस ट्रिमिंग और खाली/गलत स्ट्रिंग्स को हटाना
    for c in ["Class", "Subject", "Teacher"]:
        df[c] = df[c].astype(str).str.strip()
    
    df = df[~df["Class"].str.lower().isin(["", "nan", "none"])]
    df = df[~df["Subject"].str.lower().isin(["", "nan", "none"])]
    df = df[~df["Teacher"].str.lower().isin(["", "nan", "none"])]
    
    # पीरियड्स को पॉजिटिव इंटीजर (न्यूनतम 1) पर सेट करना
    df["Periods/Week"] = pd.to_numeric(df["Periods/Week"], errors="coerce").fillna(4).astype(int).clip(lower=1)
    return df[required].reset_index(drop=True)

def pre_check_allotments(df_allot, classes, slots_per_class):
    """सॉल्वर चलाने से पहले डेटा की प्री-चेक वैलिडेशन करता है"""
    issues = []
    warnings = []
    
    # 1. क्लास-वाइज कैपेसिटी चेक
    for c in classes:
        sub_df = df_allot[df_allot["Class"] == c]
        total_req = sub_df["Periods/Week"].sum()
        if total_req > slots_per_class:
            issues.append(f"Class '{c}': कुल माँगे गए {total_req} पीरियड, जबकि उपलब्ध केवल {slots_per_class} स्लॉट्स हैं।")
    
    # 2. टीचर-वाइज वर्कलोड ओवरलोड चेक
    teacher_totals = df_allot[df_allot["Teacher"] != "Supervised Activity"].groupby("Teacher")["Periods/Week"].sum()
    for t, total_periods in teacher_totals.items():
        if total_periods > slots_per_class:
            issues.append(f"Teacher '{t}': कुल {total_periods} पीरियड असाइन हुए हैं, जो हफ़्ते की अधिकतम सीमा ({slots_per_class} स्लॉट्स) से ज़्यादा हैं।")
        elif total_periods >= int(slots_per_class * 0.9):
            warnings.append(f"Teacher '{t}': {total_periods}/{slots_per_class} स्लॉट्स (अत्यधिक लोड - {round(total_periods/slots_per_class*100)}%)")
            
    return issues, warnings

def generate_master_excel(sch):
    """पूरे टाइमटेबल का मल्टी-शीट मास्टर एक्सेल वर्कबुक बनाता है"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        # Sheet 1: All Classes Master Grid
        all_classes_data = []
        for c in sch["classes"]:
            for d in sch["days"]:
                row = {"Class": c, "Day": d}
                for p in sch["periods"]:
                    subj, teacher = sch["schedule"].get((c, d, p), ("-", "-"))
                    row[f"Period {p}"] = "LUNCH" if subj.startswith("☕") else f"{subj} ({teacher})"
                all_classes_data.append(row)
        pd.DataFrame(all_classes_data).to_excel(writer, sheet_name="Master Schedule", index=False)
        
        # Sheet 2: Teacher Workload Summary
        workload = []
        for t in sorted(sch["teachers"]):
            cnt = sum(1 for (c, d, p), (subj, t_assigned) in sch["schedule"].items() if t_assigned == t)
            workload.append({"Teacher Name": t, "Weekly Periods": cnt, "Daily Avg": round(cnt / len(sch["days"]), 2)})
        pd.DataFrame(workload).to_excel(writer, sheet_name="Teacher Workload", index=False)

    buf.seek(0)
    return buf.getvalue()

# ================= OR-TOOLS SOLVER ENGINE =================
def solve_school_timetable(time_limit=15.0):
    w_days = int(st.session_state.working_days)
    p_per_day = int(st.session_state.periods_per_day)
    break_at = int(st.session_state.break_at)
    classes = [str(c).strip() for c in st.session_state.classes_list if str(c).strip()]
    df_allot = st.session_state.allotments_df

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][:w_days]
    all_periods = list(range(1, p_per_day + 1))
    teaching_periods = [p for p in all_periods if p != break_at]
    slots_per_class = len(days) * len(teaching_periods)

    # 1. Pre-validation checks
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
                for p in all_periods:
                    if p == break_at:
                        full_schedule[(c, d, p)] = ("☕ LUNCH / BREAK", "N/A")
                    else:
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
            "periods": all_periods,
            "break_at": break_at,
            "teachers": list(all_teachers)
        }
    else:
        return {
            "status": "failed",
            "solver_status": solver.StatusName(status),
            "message": "गणितीय रूप से यह कंस्ट्रेंट पूरा नहीं हो सकता। कृपया चेक करें कि किसी शिक्षक के पीरियड्स का योग बहुत अधिक तो नहीं है।"
        }

# ================= USER INTERFACE =================
st.title("🏫 School Timetable Pro (Deterministic & Conflict-Free)")
st.caption("Google OR-Tools CP-SAT संचालित 100% सटीक, क्लैश-फ्री स्कूल टाइमटेबल जनरेटर")

tab_setup, tab_class_view, tab_teacher_view, tab_audit = st.tabs([
    "⚙️ 1. Setup & Allotments", 
    "📅 2. Class-Wise Timetable", 
    "👨‍🏫 3. Teacher-Wise Schedule",
    "🔍 4. Conflict & Load Audit"
])

w_days = int(st.session_state.working_days)
p_per_day = int(st.session_state.periods_per_day)
b_at = int(st.session_state.break_at)
slots_per_class = w_days * (p_per_day - 1 if b_at <= p_per_day else p_per_day)

with tab_setup:
    st.subheader("1. Bell Schedule & Classes")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1: st.session_state.working_days = st.number_input("Working Days (सप्ताह में दिन)", 1, 7, int(st.session_state.working_days))
    with col_s2: st.session_state.periods_per_day = st.number_input("Periods per Day (कुल पीरियड)", 1, 15, int(st.session_state.periods_per_day))
    with col_s3: st.session_state.break_at = st.number_input("Lunch Break AFTER Period (लंच पीरियड)", 1, 15, int(st.session_state.break_at))

    classes_input = st.text_input("Classes List (अल्पविराम से अलग करें):", value=", ".join(st.session_state.classes_list))
    st.session_state.classes_list = [c.strip() for c in classes_input.split(",") if c.strip()]

    st.markdown("---")
    st.subheader("2. Faculty & Subject Allotments")

    # Excel / CSV Bulk Upload & Template Box
    with st.expander("📥 Bulk Upload from Excel / CSV (या Sample Template Download करें)", expanded=True):
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
                    st.success(f"✅ फ़ाइल सफलतापूर्वक अपलोड हुई! कुल {len(clean_df)} अलॉटमेंट्स, {clean_df['Teacher'].nunique()} शिक्षक, और {len(extracted_classes)} क्लासेज़ लोड हुईं।")
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
    total_avail_slots = len(curr_classes) * slots_per_class

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1: st.metric("Active Classes", len(curr_classes))
    with col_m2: st.metric("Active Teachers", total_teachers)
    with col_m3: st.metric("Slots Demanded", f"{total_req_periods} / {total_avail_slots}")
    with col_m4: st.metric("Slot Capacity/Class", f"{slots_per_class} slots/week")

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
        with st.spinner("Google OR-Tools CP-SAT मॉडल गणितीय समाधान निकाल रहा है..."):
            res = solve_school_timetable()
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
            for p in sch["periods"]:
                subj, teacher = sch["schedule"].get((sel_class, d, p), ("-", "-"))
                row[f"Period {p}"] = "☕ LUNCH" if subj.startswith("☕") else f"{subj}\n({teacher})"
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
            for p in sch["periods"]:
                if p == sch["break_at"]:
                    row[f"Period {p}"] = "☕ LUNCH"
                else:
                    found_c = None
                    found_s = None
                    for c in sch["classes"]:
                        s_name, t_name = sch["schedule"].get((c, d, p), ("-", "-"))
                        if t_name == sel_teacher:
                            found_c, found_s = c, s_name
                            break
                    if found_c:
                        row[f"Period {p}"] = f"{found_s} ({found_c})"
                        total_load += 1
                    else:
                        row[f"Period {p}"] = "Free"
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
        st.subheader("🔍 Mathematical Validation & Conflict Audit")
        clashes = []
        for d in sch["days"]:
            for p in sch["periods"]:
                if p == sch["break_at"]: continue
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

