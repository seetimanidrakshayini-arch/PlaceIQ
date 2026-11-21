"""Business rules shared by student and officer routes."""
import json
from datetime import date
from db import query, one, execute
from services import nlp

STATUSES = ["Applied", "Under Review", "Shortlisted", "Technical Interview", "HR Interview", "Selected", "Rejected"]
ROUNDS = ["Aptitude Round", "Technical Round", "HR Round"]


def notify(user_id, message):
    execute("INSERT INTO notifications (user_id, message) VALUES (%s,%s)", (user_id, message[:300]))


def notify_officers(message):
    for o in query("SELECT id FROM users WHERE role='officer' AND active=1"):
        notify(o["id"], message)


def f(v):
    """Decimal -> float for JSON."""
    return float(v) if v is not None else None


def iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v is not None else None)


def latest_resume(student_id):
    return one("SELECT * FROM resumes WHERE student_id=%s ORDER BY id DESC LIMIT 1", (student_id,))


def student_skills(student, resume=None):
    """Union of profile skills, languages and skills detected in the latest analysed resume."""
    texts = [student.get("skills"), student.get("languages")]
    out = nlp.skill_set(*texts)
    if resume and resume.get("analysis_json"):
        try:
            for s in json.loads(resume["analysis_json"]).get("skills_found", []):
                out[s.lower()] = s
        except ValueError:
            pass
    return out


def eligibility_reasons(student, job):
    """Mandatory criteria. Returns list of reasons (empty list = eligible)."""
    r = []
    if float(student["cgpa"]) < float(job["min_cgpa"]):
        r.append("CGPA %.2f is below required %.2f" % (float(student["cgpa"]), float(job["min_cgpa"])))
    if int(student["backlogs"]) > int(job["max_backlogs"]):
        r.append("Backlogs %d exceed allowed %d" % (int(student["backlogs"]), int(job["max_backlogs"])))
    allowed = [d.strip().upper() for d in (job.get("allowed_depts") or "").split(",") if d.strip()]
    if allowed and student["dept"].upper() not in allowed:
        r.append("Department %s is not eligible (allowed: %s)" % (student["dept"], ", ".join(allowed)))
    return r


def job_dict(j, student=None, sskills=None):
    d = {
        "id": j["id"], "company_id": j["company_id"], "company": j["company_name"],
        "industry": j.get("industry"), "role": j["role"], "description": j.get("description") or "",
        "pkg": f(j["package_lpa"]), "cgpa": f(j["min_cgpa"]), "bl": int(j["max_backlogs"]),
        "depts": [x.strip() for x in (j.get("allowed_depts") or "").split(",") if x.strip()],
        "sk": nlp.split_list(j.get("skills")), "dl": iso(j["deadline"]), "active": bool(j["active"]),
        "expired": j["deadline"] < date.today(),
    }
    if student is not None:
        m = nlp.skill_match(sskills or {}, d["sk"])
        d["match"] = m
        d["reasons"] = eligibility_reasons(student, j)
        d["eligible"] = not d["reasons"]
    return d


JOB_SELECT = ("SELECT j.*, c.name AS company_name, c.industry FROM jobs j "
              "JOIN companies c ON c.id=j.company_id ")


def app_rows(where="", args=()):
    return query(
        "SELECT a.id, a.status, a.applied_at, a.job_id, a.student_id, j.role, j.package_lpa, j.company_id, "
        "c.name AS company, s.usn, u.name AS student_name, s.dept, s.cgpa, s.backlogs "
        "FROM applications a JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id "
        "JOIN students s ON s.id=a.student_id JOIN users u ON u.id=s.user_id " + where + " ORDER BY a.applied_at DESC, a.id DESC",
        args)


def next_interview(app_id):
    return one("SELECT * FROM interviews WHERE application_id=%s ORDER BY scheduled_date DESC, id DESC LIMIT 1", (app_id,))


def interview_dict(i):
    return {"id": i["id"], "round": i["round_name"], "date": iso(i["scheduled_date"]),
            "time": str(i["scheduled_time"])[:5] if i.get("scheduled_time") is not None else "",
            "venue": i.get("venue") or "", "notes": i.get("notes") or ""}
