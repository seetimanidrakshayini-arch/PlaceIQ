"""Student-facing API: profile, resume analysis, skill gap, recommendations, applications."""
import json
import os
from collections import Counter
from datetime import date
from flask import Blueprint, jsonify, request, send_from_directory
from pymysql.err import IntegrityError

from config import Config
from db import query, one, execute
from routes.auth import login_required, err, body
from services import nlp
from services import resume_pdf
from services.core import (JOB_SELECT, STATUSES, app_rows, eligibility_reasons, f, interview_dict, iso, job_dict,
                           latest_resume, notify, notify_officers, student_skills)

bp = Blueprint("student", __name__, url_prefix="/api/student")


# ------------------------------------------------------------------ helpers
def load_student():
    return one("SELECT s.*, u.name, u.email FROM students s JOIN users u ON u.id=s.user_id WHERE s.user_id=%s",
               (request.user["id"],))


def profile_dict(s):
    return {"name": s["name"], "email": s["email"], "usn": s["usn"], "dept": s["dept"], "sem": s["semester"],
            "year": s["grad_year"], "yos": s["year_of_study"], "cgpa": f(s["cgpa"]), "backlogs": s["backlogs"],
            "tenth": f(s["tenth_pct"]), "twelfth": f(s["twelfth_pct"]), "phone": s["phone"] or "",
            "skills": s["skills"] or "", "langs": s["languages"] or "", "certs": s["certifications"] or "",
            "projects": s["projects"] or ""}


def completeness(s, resume):
    checks = [s["cgpa"] and float(s["cgpa"]) > 0, s["semester"] and s["semester"] > 0, s["grad_year"], s["phone"],
              s["skills"], s["languages"], s["certifications"], s["projects"], s["tenth_pct"], s["twelfth_pct"], resume]
    return round(100 * sum(1 for c in checks if c) / len(checks))


def active_jobs(open_only=True):
    sql = JOB_SELECT + "WHERE j.active=1 " + ("AND j.deadline>=CURDATE() " if open_only else "") + "ORDER BY j.deadline, j.id"
    return query(sql)


def jobs_with_match(s, resume, open_only=True):
    sk = student_skills(s, resume)
    return [job_dict(j, s, sk) for j in active_jobs(open_only)], sk


def num(v, lo, hi, label, cast=float, allow_none=False):
    if v in (None, ""):
        if allow_none:
            return None
        raise ValueError("%s is required." % label)
    try:
        x = cast(v)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number." % label)
    if not lo <= x <= hi:
        raise ValueError("%s must be between %s and %s." % (label, lo, hi))
    return x


# ------------------------------------------------------------------ profile
@bp.get("/profile")
@login_required("student")
def get_profile():
    s = load_student()
    r = latest_resume(s["id"])
    return jsonify({"ok": True, "profile": profile_dict(s), "completeness": completeness(s, r)})


@bp.put("/profile")
@login_required("student")
def put_profile():
    d = body()
    s = load_student()
    try:
        name = (d.get("name") or "").strip()
        if len(name) < 3:
            raise ValueError("Name is too short.")
        dept = (d.get("dept") or "").strip()
        if not one("SELECT id FROM departments WHERE name=%s", (dept,)):
            raise ValueError("Select a valid department.")
        vals = dict(
            sem=num(d.get("sem"), 1, 10, "Semester", int),
            year=num(d.get("year"), 2000, 2100, "Graduation year", int, True),
            cgpa=num(d.get("cgpa"), 0, 10, "CGPA"),
            bl=num(d.get("backlogs"), 0, 50, "Backlogs", int),
            tenth=num(d.get("tenth"), 0, 100, "10th %", float, True),
            twelfth=num(d.get("twelfth"), 0, 100, "12th %", float, True),
        )
        usn = (d.get("usn") or "").strip().upper()
        if not usn:
            raise ValueError("USN is required.")
    except ValueError as e:
        return err(str(e))
    try:
        execute("UPDATE users SET name=%s WHERE id=%s", (name, request.user["id"]))
        execute("UPDATE students SET usn=%s, dept=%s, semester=%s, grad_year=%s, cgpa=%s, backlogs=%s, tenth_pct=%s, "
                "twelfth_pct=%s, phone=%s, skills=%s, languages=%s, certifications=%s, projects=%s WHERE id=%s",
                (usn, dept, vals["sem"], vals["year"], vals["cgpa"], vals["bl"], vals["tenth"], vals["twelfth"],
                 (d.get("phone") or "").strip()[:20], (d.get("skills") or "").strip(), (d.get("langs") or "").strip(),
                 (d.get("certs") or "").strip(), (d.get("projects") or "").strip(), s["id"]))
    except IntegrityError:
        return err("This USN belongs to another student.", 409)
    s = load_student()
    return jsonify({"ok": True, "message": "Profile saved.", "profile": profile_dict(s),
                    "completeness": completeness(s, latest_resume(s["id"]))})


# ------------------------------------------------------------------ resume
def resume_payload(r):
    if not r:
        return None
    a = json.loads(r["analysis_json"]) if r["analysis_json"] else None
    return {"id": r["id"], "name": r["original_name"], "size_kb": max(1, round(r["size_bytes"] / 1024)),
            "uploaded": r["uploaded_at"].strftime("%d %b %Y %H:%M"), "review": r["review_status"],
            "review_note": r["review_note"] or "", "analysis": a}


@bp.get("/resume")
@login_required("student")
def get_resume():
    s = load_student()
    return jsonify({"ok": True, "resume": resume_payload(latest_resume(s["id"]))})


@bp.post("/resume")
@login_required("student")
def upload_resume():
    s = load_student()
    try:
        stored, size = resume_pdf.save_pdf(request.files.get("resume"))
    except resume_pdf.ResumeError as e:
        return err(str(e))
    try:
        text = resume_pdf.extract_text(stored)
    except resume_pdf.ResumeError as e:
        resume_pdf.delete_file(stored)
        return err(str(e))
    market = []
    for j in active_jobs(False):
        market += nlp.split_list(j["skills"])
    analysis = nlp.analyse_resume(text, profile_dict(s), market)
    # keep only one stored resume file per student (replace previous)
    for old in query("SELECT stored_name FROM resumes WHERE student_id=%s", (s["id"],)):
        resume_pdf.delete_file(old["stored_name"])
    execute("DELETE FROM resumes WHERE student_id=%s", (s["id"],))
    rid = execute("INSERT INTO resumes (student_id, original_name, stored_name, size_bytes, text_content, score, analysis_json) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                  (s["id"], os.path.basename(request.files["resume"].filename)[:255], stored, size, text,
                   analysis["score"], json.dumps(analysis)))
    notify(request.user["id"], "Resume analysed: score %d/100." % analysis["score"])
    notify_officers("%s uploaded a resume (AI score %d/100)." % (s["name"], analysis["score"]))
    return jsonify({"ok": True, "resume": resume_payload(one("SELECT * FROM resumes WHERE id=%s", (rid,)))})


@bp.get("/resume/file")
@login_required("student")
def resume_file():
    r = latest_resume(load_student()["id"])
    if not r:
        return err("No resume uploaded.", 404)
    return send_from_directory(Config.UPLOAD_DIR, r["stored_name"], mimetype="application/pdf", download_name=r["original_name"])


@bp.post("/resume/apply-skills")
@login_required("student")
def apply_detected_skills():
    """Merge skills detected in the resume into the student profile."""
    s = load_student()
    r = latest_resume(s["id"])
    if not r or not r["analysis_json"]:
        return err("Upload and analyse a resume first.")
    found = json.loads(r["analysis_json"]).get("skills_found", [])
    have = nlp.skill_set(s["skills"], s["languages"])
    merged = nlp.split_list(s["skills"])
    added = [x for x in found if x.lower() not in have]
    merged += added
    execute("UPDATE students SET skills=%s WHERE id=%s", (", ".join(merged), s["id"]))
    return jsonify({"ok": True, "added": added, "message": ("Added %d skill(s) to your profile." % len(added)) if added else "Your profile already has all detected skills."})


# ------------------------------------------------------------------ jobs / eligibility / matching
@bp.get("/jobs")
@login_required("student")
def jobs():
    s = load_student()
    r = latest_resume(s["id"])
    items, _ = jobs_with_match(s, r, open_only=False)
    applied = {a["job_id"]: a["status"] for a in query("SELECT job_id, status FROM applications WHERE student_id=%s", (s["id"],))}
    for j in items:
        j["applied"] = applied.get(j["id"])
    companies = query("SELECT id, name FROM companies ORDER BY name")
    return jsonify({"ok": True, "jobs": items, "companies": companies})


@bp.get("/jobs/<int:job_id>")
@login_required("student")
def job_detail(job_id):
    s = load_student()
    j = one(JOB_SELECT + "WHERE j.id=%s AND j.active=1", (job_id,))
    if not j:
        return err("Job not found.", 404)
    d = job_dict(j, s, student_skills(s, latest_resume(s["id"])))
    a = one("SELECT status FROM applications WHERE job_id=%s AND student_id=%s", (job_id, s["id"]))
    d["applied"] = a["status"] if a else None
    c = one("SELECT website FROM companies WHERE id=%s", (j["company_id"],))
    d["website"] = c["website"] if c else ""
    return jsonify({"ok": True, "job": d})


@bp.post("/apply/<int:job_id>")
@login_required("student")
def apply(job_id):
    s = load_student()
    j = one(JOB_SELECT + "WHERE j.id=%s AND j.active=1", (job_id,))
    if not j:
        return err("Job not found.", 404)
    if j["deadline"] < date.today():
        return err("The application deadline for this job has passed.")
    reasons = eligibility_reasons(s, j)
    if reasons:
        return err("Not eligible: " + reasons[0], 403)
    try:
        execute("INSERT INTO applications (job_id, student_id) VALUES (%s,%s)", (job_id, s["id"]))
    except IntegrityError:
        return err("You have already applied to this job.", 409)
    notify(request.user["id"], "Applied to %s – %s." % (j["company_name"], j["role"]))
    notify_officers("%s applied to %s – %s." % (s["name"], j["company_name"], j["role"]))
    return jsonify({"ok": True, "message": "Application submitted."})


@bp.get("/skill-gap")
@login_required("student")
def skill_gap():
    s = load_student()
    r = latest_resume(s["id"])
    items, sk = jobs_with_match(s, r, open_only=True)
    cnt, elig_cnt = Counter(), Counter()
    for j in items:
        for m in j["match"]["missing"]:
            cnt[m] += 1
            if j["eligible"]:
                elig_cnt[m] += 1
    topics = [{"skill": k, "jobs": v, "eligible_jobs": elig_cnt[k]} for k, v in
              sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:8]]
    return jsonify({"ok": True, "skills": sorted(sk.values()), "jobs": [
        {"id": j["id"], "company": j["company"], "role": j["role"], "have": j["match"]["have"],
         "missing": j["match"]["missing"], "pct": j["match"]["pct"], "eligible": j["eligible"]} for j in items],
        "topics": topics})


@bp.get("/recommendations")
@login_required("student")
def recommendations():
    s = load_student()
    r = latest_resume(s["id"])
    items, sk = jobs_with_match(s, r, open_only=True)
    if not items:
        return jsonify({"ok": True, "items": []})
    resume_text = (r["text_content"] or "")[:3000] if r else ""
    query_text = " ".join([s["skills"] or "", s["languages"] or "", s["certifications"] or "", s["projects"] or "",
                           " ".join(sk.values()), resume_text])
    docs = [" ".join([j["role"], j["description"], " ".join(j["sk"]) * 2]) for j in items]
    sims = nlp.tfidf_similarity(query_text, docs)
    top = max(sims) or 1
    for j, sim in zip(items, sims):
        j["text_sim"] = round(100 * sim / top)
        j["score"] = round(0.7 * j["match"]["pct"] + 0.3 * j["text_sim"])
    items.sort(key=lambda j: (not j["eligible"], -j["score"]))
    applied = {a["job_id"] for a in query("SELECT job_id FROM applications WHERE student_id=%s", (s["id"],))}
    for j in items:
        j["applied"] = j["id"] in applied
    return jsonify({"ok": True, "items": items})


# ------------------------------------------------------------------ applications / interviews / results
def my_apps(s):
    rows = app_rows("WHERE a.student_id=%s", (s["id"],))
    ivs = {}
    for i in query("SELECT i.* FROM interviews i JOIN applications a ON a.id=i.application_id WHERE a.student_id=%s "
                   "ORDER BY i.scheduled_date, i.id", (s["id"],)):
        ivs.setdefault(i["application_id"], []).append(interview_dict(i))
    out = []
    for a in rows:
        out.append({"id": a["id"], "job_id": a["job_id"], "company": a["company"], "role": a["role"],
                    "pkg": f(a["package_lpa"]), "date": iso(a["applied_at"])[:10], "status": a["status"],
                    "interviews": ivs.get(a["id"], [])})
    return out


@bp.get("/applications")
@login_required("student")
def applications():
    return jsonify({"ok": True, "items": my_apps(load_student())})


@bp.get("/interviews")
@login_required("student")
def interviews():
    s = load_student()
    rows = query("SELECT i.*, c.name AS company, j.role, a.status FROM interviews i JOIN applications a ON a.id=i.application_id "
                 "JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id WHERE a.student_id=%s "
                 "ORDER BY i.scheduled_date, i.scheduled_time", (s["id"],))
    return jsonify({"ok": True, "items": [dict(interview_dict(i), company=i["company"], role=i["role"], status=i["status"]) for i in rows]})


@bp.get("/results")
@login_required("student")
def results():
    s = load_student()
    apps = my_apps(s)
    sel = [a for a in apps if a["status"] == "Selected"]
    return jsonify({"ok": True, "total": len(apps),
                    "shortlisted": sum(1 for a in apps if STATUSES.index(a["status"]) >= 2 and a["status"] != "Rejected"),
                    "interviews_done": sum(1 for a in apps if a["status"] in ("HR Interview", "Selected")),
                    "selected": sel, "placed": bool(sel)})


@bp.get("/dashboard")
@login_required("student")
def dashboard():
    s = load_student()
    r = latest_resume(s["id"])
    apps = my_apps(s)
    items, _ = jobs_with_match(s, r, open_only=True)
    upcoming = query("SELECT i.*, c.name AS company, j.role FROM interviews i JOIN applications a ON a.id=i.application_id "
                     "JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id "
                     "WHERE a.student_id=%s AND i.scheduled_date>=CURDATE() ORDER BY i.scheduled_date, i.scheduled_time LIMIT 3", (s["id"],))
    notes = query("SELECT message FROM notifications WHERE user_id=%s ORDER BY id DESC LIMIT 6", (request.user["id"],))
    counts = Counter(a["status"] for a in apps)
    ra = json.loads(r["analysis_json"]) if r and r["analysis_json"] else None
    return jsonify({
        "ok": True, "profile": profile_dict(s), "completeness": completeness(s, r),
        "stats": {"jobs": len(items), "eligible": sum(1 for j in items if j["eligible"]), "applied": len(apps),
                  "shortlisted": sum(1 for a in apps if STATUSES.index(a["status"]) >= 2 and a["status"] != "Rejected"),
                  "placed": any(a["status"] == "Selected" for a in apps)},
        "status_counts": [[st, counts.get(st, 0)] for st in STATUSES],
        "resume": ({"score": ra["score"], "name": r["original_name"], "review": r["review_status"],
                    "tips": ra["recommendations"][:3], "skills": ra["skills_found"][:8]} if ra else None),
        "upcoming": [dict(interview_dict(i), company=i["company"], role=i["role"]) for i in upcoming],
        "notes": [n["message"] for n in notes],
        "recent_jobs": items[:3],
    })
