"""Placement officer API: students, companies, jobs, applications, interviews, results, reports, settings."""
import csv
import io
import json
import re
import secrets
from datetime import date, time as dtime
from flask import Blueprint, Response, jsonify, request, send_from_directory
from werkzeug.security import generate_password_hash
from pymysql.err import IntegrityError

from config import Config
from db import query, one, execute, transaction
from routes.auth import login_required, err, body, EMAIL_RE, USN_RE
from services import nlp, reports
from services.core import (JOB_SELECT, ROUNDS, STATUSES, app_rows, f, interview_dict, iso, job_dict, latest_resume,
                           notify)

bp = Blueprint("officer", __name__, url_prefix="/api/officer")


def officer(fn):
    return login_required("officer")(fn)


def to_num(v, lo, hi, label, cast=float):
    try:
        x = cast(v)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number." % label)
    if not lo <= x <= hi:
        raise ValueError("%s must be between %s and %s." % (label, lo, hi))
    return x


def get_setting(k, default=""):
    r = one("SELECT v FROM settings WHERE k=%s", (k,))
    return r["v"] if r else default


# ------------------------------------------------------------------ summary used by dashboard + reports
def summary():
    total_students = one("SELECT COUNT(*) c FROM students")["c"]
    placed = one("SELECT COUNT(DISTINCT a.student_id) c FROM applications a WHERE a.status='Selected'")["c"]
    pk = one("SELECT AVG(package_lpa) a, MAX(package_lpa) mx, MIN(package_lpa) mn FROM placement_results")
    by_status = {r["status"]: r["c"] for r in query("SELECT status, COUNT(*) c FROM applications GROUP BY status")}
    by_dept = query("SELECT s.dept, COUNT(*) total, "
                    "COUNT(DISTINCT CASE WHEN a.status='Selected' THEN s.id END) placed "
                    "FROM students s LEFT JOIN applications a ON a.student_id=s.id GROUP BY s.dept ORDER BY s.dept")
    # students per dept (not duplicated by joins)
    stu_dept = {r["dept"]: r["c"] for r in query("SELECT dept, COUNT(*) c FROM students GROUP BY dept")}
    dept_rows = []
    for r in by_dept:
        n = stu_dept.get(r["dept"], 0)
        dept_rows.append({"dept": r["dept"], "students": n, "placed": int(r["placed"]),
                          "rate": round(100 * int(r["placed"]) / n) if n else 0})
    by_company = query("SELECT c.name, COUNT(a.id) apps, COALESCE(SUM(a.status='Selected'),0) selected "
                       "FROM companies c LEFT JOIN jobs j ON j.company_id=c.id LEFT JOIN applications a ON a.job_id=j.id "
                       "GROUP BY c.id, c.name ORDER BY c.name")
    return {
        "students": total_students, "companies": one("SELECT COUNT(*) c FROM companies")["c"],
        "jobs": one("SELECT COUNT(*) c FROM jobs WHERE active=1")["c"],
        "applications": sum(by_status.values()), "placed": placed,
        "placement_rate": round(100 * placed / total_students) if total_students else 0,
        "avg_pkg": round(float(pk["a"]), 2) if pk["a"] is not None else 0,
        "max_pkg": f(pk["mx"]) or 0, "min_pkg": f(pk["mn"]) or 0,
        "by_status": [[s, int(by_status.get(s, 0))] for s in STATUSES],
        "by_dept": dept_rows,
        "by_company": [{"name": r["name"], "apps": int(r["apps"]), "selected": int(r["selected"])} for r in by_company],
    }


@bp.get("/dashboard")
@officer
def dashboard():
    s = summary()
    s["pending_reviews"] = one("SELECT COUNT(*) c FROM resumes WHERE review_status='Pending'")["c"]
    s["upcoming"] = [dict(interview_dict(i), student=i["student"], company=i["company"], role=i["role"]) for i in query(
        "SELECT i.*, u.name AS student, c.name AS company, j.role FROM interviews i JOIN applications a ON a.id=i.application_id "
        "JOIN students st ON st.id=a.student_id JOIN users u ON u.id=st.user_id JOIN jobs j ON j.id=a.job_id "
        "JOIN companies c ON c.id=j.company_id WHERE i.scheduled_date>=CURDATE() ORDER BY i.scheduled_date, i.scheduled_time LIMIT 5")]
    return jsonify({"ok": True, "summary": s})


# ------------------------------------------------------------------ students
def student_rows(where="", args=()):
    rows = query(
        "SELECT s.id, s.usn, s.dept, s.semester, s.cgpa, s.backlogs, s.phone, s.skills, u.name, u.email, u.active, "
        "(SELECT COUNT(*) FROM applications a WHERE a.student_id=s.id) apps, "
        "(SELECT COUNT(*) FROM applications a WHERE a.student_id=s.id AND a.status='Selected') offers, "
        "r.id AS rid, r.score, r.review_status, r.review_note, r.analysis_json "
        "FROM students s JOIN users u ON u.id=s.user_id "
        "LEFT JOIN resumes r ON r.id=(SELECT MAX(id) FROM resumes WHERE student_id=s.id) " + where + " ORDER BY s.usn", args)
    out = []
    for r in rows:
        skills = []
        if r["analysis_json"]:
            skills = json.loads(r["analysis_json"]).get("skills_found", [])[:6]
        out.append({"id": r["id"], "usn": r["usn"], "name": r["name"], "email": r["email"], "dept": r["dept"],
                    "sem": r["semester"], "cgpa": f(r["cgpa"]), "bl": r["backlogs"], "phone": r["phone"] or "",
                    "apps": r["apps"], "placed": r["offers"] > 0, "has_resume": r["rid"] is not None,
                    "score": r["score"], "review": r["review_status"] if r["rid"] else None,
                    "review_note": r["review_note"] or "", "skills": skills,
                    "pool": float(r["cgpa"]) >= 7.5 and r["backlogs"] == 0})
    return out


@bp.get("/students")
@officer
def students():
    return jsonify({"ok": True, "items": student_rows()})


@bp.post("/students")
@officer
def add_student():
    d = body()
    name, usn, email = (d.get("name") or "").strip(), (d.get("usn") or "").strip().upper(), (d.get("email") or "").strip().lower()
    dept = (d.get("dept") or "").strip()
    try:
        if len(name) < 3:
            raise ValueError("Enter the student's full name.")
        if not USN_RE.match(usn):
            raise ValueError("USN format should look like 1XX22CS014.")
        if not EMAIL_RE.match(email):
            raise ValueError("Enter a valid email address.")
        if not one("SELECT id FROM departments WHERE name=%s", (dept,)):
            raise ValueError("Select a valid department.")
        cgpa = to_num(d.get("cgpa") or 0, 0, 10, "CGPA")
        bl = to_num(d.get("backlogs") or 0, 0, 50, "Backlogs", int)
    except ValueError as e:
        return err(str(e))
    temp = secrets.token_urlsafe(7)
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'student')",
                            (name, email, generate_password_hash(temp)))
                uid = cur.lastrowid
                cur.execute("INSERT INTO students (user_id,usn,dept,cgpa,backlogs) VALUES (%s,%s,%s,%s,%s)", (uid, usn, dept, cgpa, bl))
        notify(uid, "Your PlaceIQ account was created by the placement office. Please change your password after login.")
    except IntegrityError as e:
        return err("This USN is already registered." if "usn" in str(e).lower() else "This email is already registered.", 409)
    return jsonify({"ok": True, "message": "Student added.", "temp_password": temp})


@bp.put("/students/<int:sid>")
@officer
def edit_student(sid):
    d = body()
    s = one("SELECT user_id FROM students WHERE id=%s", (sid,))
    if not s:
        return err("Student not found.", 404)
    try:
        cgpa = to_num(d.get("cgpa"), 0, 10, "CGPA")
        bl = to_num(d.get("backlogs"), 0, 50, "Backlogs", int)
        dept = (d.get("dept") or "").strip()
        if not one("SELECT id FROM departments WHERE name=%s", (dept,)):
            raise ValueError("Select a valid department.")
    except ValueError as e:
        return err(str(e))
    execute("UPDATE students SET cgpa=%s, backlogs=%s, dept=%s WHERE id=%s", (cgpa, bl, dept, sid))
    notify(s["user_id"], "The placement office updated your academic record (CGPA %.2f, backlogs %d)." % (cgpa, bl))
    return jsonify({"ok": True, "message": "Student updated."})


@bp.delete("/students/<int:sid>")
@officer
def delete_student(sid):
    s = one("SELECT user_id FROM students WHERE id=%s", (sid,))
    if not s:
        return err("Student not found.", 404)
    for r in query("SELECT stored_name FROM resumes WHERE student_id=%s", (sid,)):
        from services.resume_pdf import delete_file
        delete_file(r["stored_name"])
    execute("DELETE FROM users WHERE id=%s", (s["user_id"],))  # cascades to student, applications, resumes
    return jsonify({"ok": True, "message": "Student removed."})


@bp.post("/students/<int:sid>/reset-password")
@officer
def reset_password(sid):
    s = one("SELECT user_id FROM students WHERE id=%s", (sid,))
    if not s:
        return err("Student not found.", 404)
    temp = secrets.token_urlsafe(7)
    execute("UPDATE users SET password_hash=%s WHERE id=%s", (generate_password_hash(temp), s["user_id"]))
    return jsonify({"ok": True, "temp_password": temp})


@bp.get("/students/<int:sid>/resume-file")
@officer
def student_resume_file(sid):
    r = latest_resume(sid)
    if not r:
        return err("This student has not uploaded a resume.", 404)
    return send_from_directory(Config.UPLOAD_DIR, r["stored_name"], mimetype="application/pdf", download_name=r["original_name"])


@bp.get("/students/<int:sid>/resume")
@officer
def student_resume(sid):
    st = student_rows("WHERE s.id=%s", (sid,))
    if not st:
        return err("Student not found.", 404)
    r = latest_resume(sid)
    return jsonify({"ok": True, "student": st[0], "resume": (
        {"name": r["original_name"], "review": r["review_status"], "note": r["review_note"] or "",
         "analysis": json.loads(r["analysis_json"]) if r["analysis_json"] else None} if r else None)})


@bp.post("/students/<int:sid>/review")
@officer
def review_resume(sid):
    d = body()
    status = d.get("status")
    if status not in ("Approved", "Changes requested", "Pending"):
        return err("Invalid review status.")
    r = latest_resume(sid)
    if not r:
        return err("This student has not uploaded a resume.", 404)
    note = (d.get("note") or "").strip()[:500]
    execute("UPDATE resumes SET review_status=%s, review_note=%s WHERE id=%s", (status, note, r["id"]))
    u = one("SELECT user_id FROM students WHERE id=%s", (sid,))
    notify(u["user_id"], "Your resume was reviewed: %s%s" % (status, (" – " + note) if note else "."))
    return jsonify({"ok": True, "message": "Resume review: %s" % status})


# ------------------------------------------------------------------ companies
@bp.get("/companies")
@officer
def companies():
    rows = query("SELECT c.*, (SELECT COUNT(*) FROM jobs j WHERE j.company_id=c.id) jobs FROM companies c ORDER BY c.name")
    return jsonify({"ok": True, "items": [{"id": r["id"], "name": r["name"], "ind": r["industry"] or "", "site": r["website"] or "",
                                             "jobs": r["jobs"]} for r in rows]})


@bp.post("/companies")
@officer
def add_company():
    d = body()
    name = (d.get("name") or "").strip()
    if len(name) < 2:
        return err("Enter the company name.")
    try:
        execute("INSERT INTO companies (name, industry, website) VALUES (%s,%s,%s)",
                (name[:120], (d.get("ind") or "").strip()[:80], (d.get("site") or "").strip()[:160]))
    except IntegrityError:
        return err("A company with this name already exists.", 409)
    return jsonify({"ok": True, "message": "Company added."})


@bp.put("/companies/<int:cid>")
@officer
def edit_company(cid):
    d = body()
    name = (d.get("name") or "").strip()
    if len(name) < 2:
        return err("Enter the company name.")
    try:
        execute("UPDATE companies SET name=%s, industry=%s, website=%s WHERE id=%s",
                (name[:120], (d.get("ind") or "").strip()[:80], (d.get("site") or "").strip()[:160], cid))
    except IntegrityError:
        return err("A company with this name already exists.", 409)
    return jsonify({"ok": True, "message": "Company updated."})


@bp.delete("/companies/<int:cid>")
@officer
def delete_company(cid):
    if one("SELECT 1 x FROM applications a JOIN jobs j ON j.id=a.job_id WHERE j.company_id=%s LIMIT 1", (cid,)):
        return err("This company has applications. Close its jobs instead of deleting it.", 409)
    execute("DELETE FROM companies WHERE id=%s", (cid,))
    return jsonify({"ok": True, "message": "Company removed."})


# ------------------------------------------------------------------ jobs
def job_fields(d):
    role = (d.get("role") or "").strip()
    if len(role) < 2:
        raise ValueError("Enter the job role.")
    cid = to_num(d.get("company_id"), 1, 10 ** 9, "Company", int)
    if not one("SELECT id FROM companies WHERE id=%s", (cid,)):
        raise ValueError("Select a valid company.")
    try:
        dl = date.fromisoformat((d.get("dl") or "").strip())
    except ValueError:
        raise ValueError("Enter a valid deadline date.")
    depts = [x.strip() for x in re.split(r"[,;]", d.get("depts") or "") if x.strip()]
    known = {r["name"].upper() for r in query("SELECT name FROM departments")}
    bad = [x for x in depts if x.upper() not in known]
    if bad:
        raise ValueError("Unknown department(s): " + ", ".join(bad))
    skills = ", ".join(nlp.split_list(d.get("sk") or ""))
    return (cid, role[:120], (d.get("description") or "").strip(), to_num(d.get("pkg") or 0, 0, 999, "Package"),
            to_num(d.get("cgpa") or 0, 0, 10, "Min CGPA"), to_num(d.get("bl") or 0, 0, 50, "Max backlogs", int),
            ", ".join(depts), skills, dl)


@bp.get("/jobs")
@officer
def jobs():
    rows = query(JOB_SELECT + "ORDER BY j.active DESC, j.deadline DESC, j.id DESC")
    counts = {r["job_id"]: r["c"] for r in query("SELECT job_id, COUNT(*) c FROM applications GROUP BY job_id")}
    items = []
    for j in rows:
        d = job_dict(j)
        d["applications"] = counts.get(j["id"], 0)
        items.append(d)
    return jsonify({"ok": True, "items": items})


@bp.post("/jobs")
@officer
def add_job():
    try:
        v = job_fields(body())
    except ValueError as e:
        return err(str(e))
    execute("INSERT INTO jobs (company_id, role, description, package_lpa, min_cgpa, max_backlogs, allowed_depts, skills, deadline) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", v)
    # tell eligible students a job is open
    j = one("SELECT c.name FROM companies c WHERE c.id=%s", (v[0],))
    for s in query("SELECT user_id, dept, cgpa, backlogs FROM students"):
        allowed = [x.strip().upper() for x in v[6].split(",") if x.strip()]
        if float(s["cgpa"]) >= float(v[4]) and s["backlogs"] <= v[5] and (not allowed or s["dept"].upper() in allowed):
            notify(s["user_id"], "New opening: %s – %s (₹%s LPA). Deadline %s." % (j["name"], v[1], v[3], v[8].isoformat()))
    return jsonify({"ok": True, "message": "Job posted."})


@bp.put("/jobs/<int:jid>")
@officer
def edit_job(jid):
    d = body()
    if not one("SELECT id FROM jobs WHERE id=%s", (jid,)):
        return err("Job not found.", 404)
    if set(d.keys()) == {"active"}:  # close / reopen
        execute("UPDATE jobs SET active=%s WHERE id=%s", (1 if d["active"] else 0, jid))
        return jsonify({"ok": True, "message": "Job reopened." if d["active"] else "Job closed."})
    try:
        v = job_fields(d)
    except ValueError as e:
        return err(str(e))
    execute("UPDATE jobs SET company_id=%s, role=%s, description=%s, package_lpa=%s, min_cgpa=%s, max_backlogs=%s, "
            "allowed_depts=%s, skills=%s, deadline=%s WHERE id=%s", v + (jid,))
    return jsonify({"ok": True, "message": "Job updated."})


@bp.delete("/jobs/<int:jid>")
@officer
def delete_job(jid):
    if one("SELECT 1 x FROM applications WHERE job_id=%s LIMIT 1", (jid,)):
        return err("This job has applications. Close it instead of removing it.", 409)
    execute("DELETE FROM jobs WHERE id=%s", (jid,))
    return jsonify({"ok": True, "message": "Job removed."})


# ------------------------------------------------------------------ applications
def apps_payload(where="", args=()):
    rows = app_rows(where, args)
    ivs = {}
    for i in query("SELECT * FROM interviews ORDER BY scheduled_date, id"):
        ivs.setdefault(i["application_id"], []).append(interview_dict(i))
    return [{"id": a["id"], "student_id": a["student_id"], "student": a["student_name"], "usn": a["usn"], "dept": a["dept"],
             "company": a["company"], "role": a["role"], "pkg": f(a["package_lpa"]), "date": iso(a["applied_at"])[:10],
             "status": a["status"], "cgpa": f(a["cgpa"]), "bl": a["backlogs"], "interviews": ivs.get(a["id"], [])} for a in rows]


@bp.get("/applications")
@officer
def applications():
    return jsonify({"ok": True, "items": apps_payload(), "statuses": STATUSES})


@bp.put("/applications/<int:aid>/status")
@officer
def set_status(aid):
    status = body().get("status")
    if status not in STATUSES:
        return err("Invalid status.")
    a = one("SELECT a.*, j.package_lpa, j.role, c.name AS company, s.user_id FROM applications a JOIN jobs j ON j.id=a.job_id "
            "JOIN companies c ON c.id=j.company_id JOIN students s ON s.id=a.student_id WHERE a.id=%s", (aid,))
    if not a:
        return err("Application not found.", 404)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE applications SET status=%s WHERE id=%s", (status, aid))
            if status == "Selected":
                cur.execute("INSERT INTO placement_results (application_id, package_lpa, declared_on) VALUES (%s,%s,CURDATE()) "
                            "ON DUPLICATE KEY UPDATE package_lpa=VALUES(package_lpa)", (aid, a["package_lpa"]))
            else:
                cur.execute("DELETE FROM placement_results WHERE application_id=%s", (aid,))
    msg = "%s – %s: your status is now %s." % (a["company"], a["role"], status)
    if status == "Selected":
        msg = "🎉 Congratulations! You were selected by %s for %s." % (a["company"], a["role"])
    notify(a["user_id"], msg)
    return jsonify({"ok": True, "message": "Status updated to %s." % status})


# ------------------------------------------------------------------ interviews
@bp.get("/interviews")
@officer
def interviews():
    return jsonify({"ok": True, "items": apps_payload(), "rounds": ROUNDS})


@bp.post("/interviews")
@officer
def schedule_interview():
    d = body()
    a = one("SELECT a.*, j.role, c.name AS company, s.user_id FROM applications a JOIN jobs j ON j.id=a.job_id "
            "JOIN companies c ON c.id=j.company_id JOIN students s ON s.id=a.student_id WHERE a.id=%s", (d.get("application_id"),))
    if not a:
        return err("Application not found.", 404)
    rnd = d.get("round")
    if rnd not in ROUNDS:
        return err("Choose a valid round.")
    if a["status"] in ("Rejected", "Selected"):
        return err("Cannot schedule an interview for an application that is already %s." % a["status"])
    try:
        day = date.fromisoformat((d.get("date") or "").strip())
    except ValueError:
        return err("Enter a valid interview date.")
    tm = None
    if (d.get("time") or "").strip():
        try:
            hh, mm = (d["time"].strip().split(":") + ["0"])[:2]
            tm = dtime(int(hh), int(mm))
        except ValueError:
            return err("Enter a valid time (HH:MM).")
    venue, notes = (d.get("venue") or "").strip()[:160], (d.get("notes") or "").strip()[:300]
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO interviews (application_id, round_name, scheduled_date, scheduled_time, venue, notes) "
                        "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE scheduled_date=VALUES(scheduled_date), "
                        "scheduled_time=VALUES(scheduled_time), venue=VALUES(venue), notes=VALUES(notes)",
                        (a["id"], rnd, day, tm, venue, notes))
            new = {"Aptitude Round": "Shortlisted" if a["status"] in ("Applied", "Under Review") else a["status"],
                   "Technical Round": "Technical Interview", "HR Round": "HR Interview"}[rnd]
            cur.execute("UPDATE applications SET status=%s WHERE id=%s", (new, a["id"]))
    notify(a["user_id"], "%s – %s: %s scheduled on %s%s%s." % (
        a["company"], a["role"], rnd, day.strftime("%d %b %Y"), (" at " + tm.strftime("%H:%M")) if tm else "",
        (", " + venue) if venue else ""))
    return jsonify({"ok": True, "message": "%s scheduled." % rnd})


@bp.delete("/interviews/<int:iid>")
@officer
def delete_interview(iid):
    execute("DELETE FROM interviews WHERE id=%s", (iid,))
    return jsonify({"ok": True, "message": "Interview removed."})


# ------------------------------------------------------------------ placement results / reports
@bp.get("/results")
@officer
def results():
    items = apps_payload()
    s = summary()
    return jsonify({"ok": True, "items": items, "summary": {
        "applications": len(items), "selected": sum(1 for a in items if a["status"] == "Selected"),
        "rejected": sum(1 for a in items if a["status"] == "Rejected"), "avg_pkg": s["avg_pkg"],
        "placed_students": s["placed"], "max_pkg": s["max_pkg"]}})


@bp.get("/reports/summary")
@officer
def report_summary():
    return jsonify({"ok": True, "summary": summary()})


@bp.get("/reports/export.csv")
@officer
def export_csv():
    kind = request.args.get("type", "applications")
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == "students":
        w.writerow(["USN", "Name", "Email", "Department", "Semester", "CGPA", "Backlogs", "Resume score", "Applications", "Placed"])
        for s in student_rows():
            w.writerow([s["usn"], s["name"], s["email"], s["dept"], s["sem"], s["cgpa"], s["bl"], s["score"] or "", s["apps"], "Yes" if s["placed"] else "No"])
    elif kind == "placements":
        w.writerow(["USN", "Student", "Department", "Company", "Role", "Package (LPA)", "Declared on"])
        for r in query("SELECT s.usn, u.name, s.dept, c.name company, j.role, p.package_lpa, p.declared_on FROM placement_results p "
                       "JOIN applications a ON a.id=p.application_id JOIN students s ON s.id=a.student_id JOIN users u ON u.id=s.user_id "
                       "JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id ORDER BY p.declared_on DESC"):
            w.writerow([r["usn"], r["name"], r["dept"], r["company"], r["role"], r["package_lpa"], iso(r["declared_on"])])
    else:
        w.writerow(["Application ID", "USN", "Student", "Department", "Company", "Role", "Applied on", "Status"])
        for a in apps_payload():
            w.writerow([a["id"], a["usn"], a["student"], a["dept"], a["company"], a["role"], a["date"], a["status"]])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=placeiq_%s.csv" % kind})


@bp.get("/reports/placement.pdf")
@officer
def export_pdf():
    s = summary()
    placed = query("SELECT s.usn, u.name, s.dept, c.name company, j.role, p.package_lpa FROM placement_results p "
                   "JOIN applications a ON a.id=p.application_id JOIN students s ON s.id=a.student_id JOIN users u ON u.id=s.user_id "
                   "JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id ORDER BY c.name, u.name")
    data = reports.build_pdf(get_setting("institution", "Institution"), get_setting("season", ""), s, placed)
    return Response(data, mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=PlaceIQ_Placement_Report.pdf"})


# ------------------------------------------------------------------ settings & departments
@bp.get("/settings")
@officer
def get_settings():
    return jsonify({"ok": True, "institution": get_setting("institution", ""), "season": get_setting("season", ""),
                    "departments": [r["name"] for r in query("SELECT name FROM departments ORDER BY name")]})


@bp.put("/settings")
@officer
def put_settings():
    d = body()
    for k in ("institution", "season"):
        v = (d.get(k) or "").strip()[:120]
        execute("INSERT INTO settings (k, v) VALUES (%s,%s) ON DUPLICATE KEY UPDATE v=VALUES(v)", (k, v))
    return jsonify({"ok": True, "message": "Settings saved."})


@bp.post("/departments")
@officer
def add_department():
    name = (body().get("name") or "").strip().upper()[:60]
    if not name:
        return err("Enter a department name.")
    try:
        execute("INSERT INTO departments (name) VALUES (%s)", (name,))
    except IntegrityError:
        return err("Department already exists.", 409)
    return jsonify({"ok": True, "message": "Department added."})


@bp.delete("/departments/<name>")
@officer
def delete_department(name):
    if one("SELECT 1 x FROM students WHERE dept=%s LIMIT 1", (name,)):
        return err("Students belong to this department; it cannot be removed.", 409)
    execute("DELETE FROM departments WHERE name=%s", (name,))
    return jsonify({"ok": True, "message": "Department removed."})
