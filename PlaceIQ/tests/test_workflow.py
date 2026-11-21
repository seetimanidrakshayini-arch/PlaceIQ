"""
End-to-end test of the complete PlaceIQ workflow against a REAL MySQL database.

    1. Configure .env (use a throw-away DB name such as placeiq_test)
    2. python database/init_db.py --reset
    3. pytest -v

WARNING: tests create data; never point them at a database holding real records.
"""
import io
import os
import sys
import uuid
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from services import nlp            # noqa: E402

RESUME_LINES = [
    "Priya Nair", "priya.nair@example.com | +91 98765 43210 | github.com/priyanair | linkedin.com/in/priyanair",
    "Summary", "Final year CSE student seeking a backend developer role.",
    "Education", "B.E. Computer Science, CGPA 8.9, 2026",
    "Skills", "Python, Flask, MySQL, SQL, Git, Docker, REST API, Data Structures, HTML, CSS, JavaScript",
    "Projects",
    "Placement Portal - Built a Flask and MySQL application that served 300+ students and reduced manual work by 40%.",
    "Weather App - Developed a JavaScript dashboard integrating public APIs and deployed it with Docker.",
    "Experience", "Software Intern, Acme Labs - Implemented REST API endpoints and automated testing.",
    "Certifications", "NPTEL Python for Everybody; AWS Cloud Practitioner",
]


def make_pdf(lines):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for ln in lines:
        c.drawString(40, y, ln[:110])
        y -= 18
    c.save()
    buf.seek(0)
    return buf


@pytest.fixture(scope="module")
def app():
    a = create_app()
    a.config["TESTING"] = True
    return a


@pytest.fixture(scope="module")
def ids():
    return {"sfx": uuid.uuid4().hex[:5]}


def login(app, email, pw, role):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": email, "password": pw, "role": role})
    assert r.status_code == 200, r.get_json()
    return c


# ---------------------------------------------------------------- NLP unit tests (no DB)
def test_nlp_skill_extraction_and_score():
    text = "\n".join(RESUME_LINES)
    a = nlp.analyse_resume(text, {"skills": "Python, Excel"}, ["Docker", "Kubernetes", "Kubernetes"])
    assert {"Python", "Flask", "MySQL", "Docker", "REST API", "JavaScript"} <= set(a["skills_found"])
    assert a["score"] >= 75, a
    assert "Kubernetes" in a["suggested_skills"]
    assert a["contact"]["email"] == "priya.nair@example.com"
    inline = nlp.analyse_resume("Ravi K\nravi@example.com 9876543210\nSKILLS: Python, SQL, Git\nEDUCATION: B.E. CSE CGPA 8.1\nPROJECTS: Chat app built with Flask")
    assert {"skills", "education", "projects"} <= set(inline["sections_present"]), inline["sections_present"]
    weak = nlp.analyse_resume("John\nI like computers and games. " * 5)
    assert weak["score"] < 35 and len(weak["recommendations"]) >= 4


def test_nlp_matching_and_tfidf():
    have = nlp.skill_set("Python, Postgres, js")
    m = nlp.skill_match(have, ["Python", "PostgreSQL", "JavaScript", "Docker"])
    assert m["pct"] == 75 and m["missing"] == ["Docker"]
    sims = nlp.tfidf_similarity("python flask mysql backend", ["python flask api backend", "autocad solidworks design"])
    assert sims[0] > sims[1]


# ---------------------------------------------------------------- full workflow
def test_health(app):
    r = app.test_client().get("/api/health")
    assert r.get_json()["db"] == "connected"
    assert app.test_client().get("/").status_code == 200
    assert app.test_client().get("/static/css/style.css").status_code == 200
    for f in ("api.js", "ui.js", "student.js", "officer.js", "app.js"):
        assert app.test_client().get("/static/js/" + f).status_code == 200, f


def test_full_flow(app, ids):
    sfx = ids["sfx"]
    email, usn = "priya%s@example.com" % sfx, "1XX22CS%s" % ("%03d" % (int(sfx, 16) % 1000))
    anon = app.test_client()

    # access control
    assert anon.get("/api/student/profile").status_code == 401
    assert anon.get("/api/officer/students").status_code == 401

    # registration validation + success
    assert anon.post("/api/auth/register", json={"name": "Pr", "usn": usn, "email": email, "password": "secret1", "confirm": "secret1", "dept": "CSE"}).status_code == 400
    assert anon.post("/api/auth/register", json={"name": "Priya Nair", "usn": "BAD", "email": email, "password": "secret1", "confirm": "secret1", "dept": "CSE"}).status_code == 400
    r = anon.post("/api/auth/register", json={"name": "Priya Nair", "usn": usn, "email": email, "password": "secret1", "confirm": "secret1", "dept": "CSE", "year_of_study": 4})
    assert r.status_code == 200, r.get_json()
    assert anon.post("/api/auth/register", json={"name": "Priya Nair", "usn": usn, "email": email, "password": "secret1", "confirm": "secret1", "dept": "CSE"}).status_code == 409

    # login: wrong password / wrong role portal
    assert anon.post("/api/auth/login", json={"email": email, "password": "nope", "role": "student"}).status_code == 401
    assert anon.post("/api/auth/login", json={"email": email, "password": "secret1", "role": "officer"}).status_code == 401
    st = login(app, email, "secret1", "student")
    assert st.get("/api/officer/students").status_code == 403

    # profile
    r = st.put("/api/student/profile", json={"name": "Priya Nair", "usn": usn, "dept": "CSE", "sem": 7, "year": 2026, "cgpa": 8.9, "backlogs": 0,
                                              "tenth": 92, "twelfth": 90, "phone": "9876543210", "skills": "Python, Flask",
                                              "langs": "Python, SQL", "certs": "NPTEL Python", "projects": "Placement Portal"})
    assert r.status_code == 200 and r.get_json()["completeness"] >= 80, r.get_json()
    assert st.put("/api/student/profile", json={"name": "Priya Nair", "usn": usn, "dept": "CSE", "sem": 7, "cgpa": 11, "backlogs": 0}).status_code == 400

    # resume upload rejects non-PDF / fake PDF, accepts real, analyses
    assert st.post("/api/student/resume", data={"resume": (io.BytesIO(b"hello"), "x.txt")}, content_type="multipart/form-data").status_code == 400
    assert st.post("/api/student/resume", data={"resume": (io.BytesIO(b"not a pdf"), "x.pdf")}, content_type="multipart/form-data").status_code == 400
    r = st.post("/api/student/resume", data={"resume": (make_pdf(RESUME_LINES), "priya_resume.pdf")}, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    an = r.get_json()["resume"]["analysis"]
    assert an["score"] >= 70 and "Flask" in an["skills_found"]
    assert st.get("/api/student/resume/file").mimetype == "application/pdf"
    added = st.post("/api/student/resume/apply-skills").get_json()
    assert "Docker" in added["added"]

    # dashboard shows resume analysis
    dash = st.get("/api/student/dashboard").get_json()
    assert dash["resume"]["score"] == an["score"]

    # officer creates company + jobs with eligibility
    off = login(app, Config.OFFICER_EMAIL, Config.OFFICER_PASSWORD, "officer")
    assert off.post("/api/officer/companies", json={"name": "TestCo " + sfx, "ind": "Software", "site": "testco.example"}).status_code == 200
    assert off.post("/api/officer/companies", json={"name": "TestCo " + sfx}).status_code == 409
    cid = [c for c in off.get("/api/officer/companies").get_json()["items"] if c["name"] == "TestCo " + sfx][0]["id"]
    dl = (date.today() + timedelta(days=20)).isoformat()
    base = {"company_id": cid, "dl": dl, "pkg": 12, "cgpa": 8.0, "bl": 0, "depts": "CSE,ISE", "sk": "Python, Flask, Docker, Kubernetes",
            "description": "Backend python flask services"}
    assert off.post("/api/officer/jobs", json=dict(base, role="Backend Engineer " + sfx)).status_code == 200
    assert off.post("/api/officer/jobs", json=dict(base, role="Elite Role " + sfx, cgpa=9.8)).status_code == 200
    assert off.post("/api/officer/jobs", json=dict(base, role="ECE Only " + sfx, depts="ECE")).status_code == 200
    assert off.post("/api/officer/jobs", json=dict(base, role="Bad", depts="XYZ")).status_code == 400
    assert off.post("/api/officer/jobs", json=dict(base, role="Past " + sfx, dl=(date.today() - timedelta(days=1)).isoformat())).status_code == 200
    jobs = {j["role"]: j for j in off.get("/api/officer/jobs").get_json()["items"]}

    # student sees eligibility, skill gap, recommendations
    sj = {j["role"]: j for j in st.get("/api/student/jobs").get_json()["jobs"]}
    good, elite, ece, past = (sj["Backend Engineer " + sfx], sj["Elite Role " + sfx], sj["ECE Only " + sfx], sj["Past " + sfx])
    assert good["eligible"] and good["match"]["pct"] == 75 and good["match"]["missing"] == ["Kubernetes"]
    assert not elite["eligible"] and "CGPA" in elite["reasons"][0]
    assert not ece["eligible"] and "Department" in ece["reasons"][0]
    assert st.get("/api/student/dashboard").get_json()["stats"]["eligible"] >= 1
    gap = st.get("/api/student/skill-gap").get_json()
    assert any(t["skill"] == "Kubernetes" for t in gap["topics"])
    recs = st.get("/api/student/recommendations").get_json()["items"]
    assert recs and recs[0]["eligible"] and all("score" in r for r in recs)
    assert [r["role"] for r in recs if r["role"] == "Backend Engineer " + sfx]

    # apply rules
    assert st.post("/api/student/apply/%d" % elite["id"]).status_code == 403
    assert st.post("/api/student/apply/%d" % ece["id"]).status_code == 403
    assert st.post("/api/student/apply/%d" % past["id"]).status_code == 400
    assert st.post("/api/student/apply/%d" % good["id"]).status_code == 200
    assert st.post("/api/student/apply/%d" % good["id"]).status_code == 409
    apps = st.get("/api/student/applications").get_json()["items"]
    mine = [a for a in apps if a["job_id"] == good["id"]][0]
    assert mine["status"] == "Applied"

    # officer reviews resume, shortlists, schedules, selects
    sid = [s for s in off.get("/api/officer/students").get_json()["items"] if s["usn"] == usn][0]["id"]
    assert off.get("/api/officer/students/%d/resume-file" % sid).mimetype == "application/pdf"
    assert off.post("/api/officer/students/%d/review" % sid, json={"status": "Approved", "note": "Good"}).status_code == 200
    oa = [a for a in off.get("/api/officer/applications").get_json()["items"] if a["id"] == mine["id"]][0]
    assert off.put("/api/officer/applications/%d/status" % oa["id"], json={"status": "Bogus"}).status_code == 400
    assert off.put("/api/officer/applications/%d/status" % oa["id"], json={"status": "Shortlisted"}).status_code == 200
    day = (date.today() + timedelta(days=3)).isoformat()
    assert off.post("/api/officer/interviews", json={"application_id": oa["id"], "round": "Technical Round", "date": day, "time": "10:30", "venue": "Lab 2"}).status_code == 200
    assert off.post("/api/officer/interviews", json={"application_id": oa["id"], "round": "Technical Round", "date": "garbage"}).status_code == 400
    assert st.get("/api/student/applications").get_json()["items"][0]["status"] == "Technical Interview"
    ivs = st.get("/api/student/interviews").get_json()["items"]
    assert ivs and ivs[0]["venue"] == "Lab 2" and ivs[0]["time"] == "10:30"
    assert off.post("/api/officer/interviews", json={"application_id": oa["id"], "round": "HR Round", "date": day}).status_code == 200
    assert off.put("/api/officer/applications/%d/status" % oa["id"], json={"status": "Selected"}).status_code == 200
    res = st.get("/api/student/results").get_json()
    assert res["placed"] and res["selected"][0]["pkg"] == 12
    o_res = off.get("/api/officer/results").get_json()
    assert o_res["summary"]["selected"] >= 1 and o_res["summary"]["avg_pkg"] > 0
    # cannot schedule after selection
    assert off.post("/api/officer/interviews", json={"application_id": oa["id"], "round": "Aptitude Round", "date": day}).status_code == 400
    # notifications delivered to the student
    msgs = [n["message"] for n in st.get("/api/auth/notifications").get_json()["items"]]
    assert any("selected" in m.lower() for m in msgs) and any("scheduled" in m for m in msgs)

    # reports
    sm = off.get("/api/officer/reports/summary").get_json()["summary"]
    assert sm["placed"] >= 1 and sm["placement_rate"] >= 1
    pdf = off.get("/api/officer/reports/placement.pdf")
    assert pdf.mimetype == "application/pdf" and pdf.data.startswith(b"%PDF")
    for kind in ("applications", "students", "placements"):
        c = off.get("/api/officer/reports/export.csv?type=" + kind)
        assert c.status_code == 200 and c.mimetype == "text/csv" and len(c.data) > 30
    assert usn.encode() in off.get("/api/officer/reports/export.csv?type=placements").data

    # job cannot be deleted while it has applications, but can be closed
    assert off.delete("/api/officer/jobs/%d" % good["id"]).status_code == 409
    assert off.put("/api/officer/jobs/%d" % good["id"], json={"active": False}).status_code == 200
    assert good["id"] not in [j["id"] for j in st.get("/api/student/jobs").get_json()["jobs"]]
    assert off.delete("/api/officer/jobs/%d" % ece["id"]).status_code == 200

    # officer student management
    r = off.post("/api/officer/students", json={"name": "Added Student", "usn": "1XX22IS%03d" % (int(sfx, 16) % 1000 + 0), "email": "added%s@example.com" % sfx, "dept": "ISE", "cgpa": 7.7, "backlogs": 0})
    assert r.status_code in (200, 409), r.get_json()
    if r.status_code == 200:
        temp = r.get_json()["temp_password"]
        login(app, "added%s@example.com" % sfx, temp, "student")
    assert off.put("/api/officer/students/%d" % sid, json={"cgpa": 9.0, "backlogs": 0, "dept": "CSE"}).status_code == 200

    # change password + officer creation guard
    assert st.post("/api/auth/change-password", json={"current": "wrong", "new": "another1"}).status_code == 403
    assert st.post("/api/auth/change-password", json={"current": "secret1", "new": "another1"}).status_code == 200
    login(app, email, "another1", "student")
    assert anon.post("/api/auth/officer-register", json={"operator_id": "bad", "code": "x", "name": "Officer X", "email": "ox@example.com", "password": "longpassword", "confirm": "longpassword"}).status_code == 403
    r = anon.post("/api/auth/officer-register", json={"operator_id": "OP-2026-07", "code": Config.OFFICER_SIGNUP_CODE, "name": "Officer %s" % sfx,
                                                      "email": "off%s@example.com" % sfx, "password": "longpassword", "confirm": "longpassword"})
    assert r.status_code == 200, r.get_json()
    login(app, "off%s@example.com" % sfx, "longpassword", "officer")

    # student removal cascades
    assert off.delete("/api/officer/students/%d" % sid).status_code == 200
    assert anon.post("/api/auth/login", json={"email": email, "password": "another1", "role": "student"}).status_code == 401
