# 🎓 PlaceIQ – AI-Powered Student Placement Tracking & Resume Analysis

Full-stack version of the PlaceIQ prototype. The original look and layout are preserved (the prototype's CSS is
used unchanged); everything that was sample data in the browser is now stored in **MySQL** and served by **Flask**.

**Stack:** HTML · CSS · JavaScript (no framework) · Python 3.10+ · Flask · MySQL (PyMySQL) · Python NLP (pure Python) · pypdf · ReportLab

**Roles (exactly two):** Student · Placement Officer

---

## 1. Features

| Student | Placement Officer |
|---|---|
| Register / login (hashed passwords, session cookies) | Login; extra officer accounts via guarded sign-up |
| Dashboard: stats, resume score, upcoming interviews, activity | Dashboard: totals, status & department charts, upcoming interviews |
| Academic profile (CGPA, backlogs, 10th/12th, skills, languages, certifications, projects) | Student management: add, edit academic record, reset password, remove, view resume PDF, CSV export |
| **PDF resume upload → NLP analysis**: score /100, breakdown, skills, projects, missing sections, suggestions, profile consistency | **AI resume review** of every student; approve / request changes with a note |
| Skill-gap analysis per job + learning topics | Company management (add / edit / remove) |
| Job recommendations (skill overlap + TF-IDF similarity) | Job postings with eligibility: min CGPA, max backlogs, allowed departments, skills, deadline; edit / close / reopen / remove |
| Eligibility checker (CGPA, backlogs, department, deadline) | Application review, shortlisting, any status change, filters, CSV export |
| Apply to jobs; status tracking | Interview scheduling (Aptitude / Technical / HR, date, time, venue) |
| Interview schedule, placement result | Placement results (Select / Reject), average / highest package |
| In-app notifications | Reports: charts, department-wise rates, **PDF report**, CSV exports; settings & departments |

---

## 2. Project structure

```
PlaceIQ/
├── app.py                 # Flask app factory + entry point
├── config.py              # Reads .env
├── db.py                  # PyMySQL helpers
├── requirements.txt
├── .env.example           # copy to .env
├── .gitignore
├── README.md
├── routes/
│   ├── auth.py            # register, login, logout, officer creation, password, notifications
│   ├── student.py         # profile, resume, jobs, skill gap, recommendations, applications …
│   └── officer.py         # students, companies, jobs, applications, interviews, reports, settings
├── services/
│   ├── nlp.py             # skill taxonomy, resume scoring, skill match, TF-IDF similarity
│   ├── resume_pdf.py      # PDF validation, storage, text extraction
│   ├── core.py            # eligibility rules, shared queries, notifications
│   └── reports.py         # PDF report (ReportLab)
├── database/
│   ├── schema.sql         # all tables
│   └── init_db.py         # creates DB + tables + departments + default officer (+ optional demo data)
├── static/
│   ├── index.html         # single-page app shell
│   ├── css/style.css      # original prototype CSS (+ a few additions at the bottom)
│   └── js/                # api.js, ui.js, app.js, student.js, officer.js, boot.js
├── uploads/resumes/       # uploaded PDFs (git-ignored)
└── tests/test_workflow.py # end-to-end tests against MySQL
```

---

## 3. Setup (VS Code)

### Prerequisites
* Python 3.10 or newer
* MySQL 8 (or MariaDB 10.3+) running locally, with a user that may create databases (e.g. `root`)

### Steps

```bash
# 1. open the extracted PlaceIQ folder in VS Code, then open a terminal (Ctrl+`)

# 2. create and activate a virtual environment
python -m venv venv
#   Windows (PowerShell):   venv\Scripts\Activate.ps1
#   Windows (cmd):          venv\Scripts\activate.bat
#   macOS / Linux:          source venv/bin/activate

# 3. install dependencies
pip install -r requirements.txt

# 4. create your settings file
#   Windows:  copy .env.example .env        macOS/Linux:  cp .env.example .env
#   then EDIT .env  (see "Manual configuration" below)

# 5. create the database, tables, departments and the officer account
python database/init_db.py            # add --demo to also load sample students/companies/jobs

# 6. run
python app.py
```

Open **http://127.0.0.1:5000**. In VS Code, select the interpreter from `venv` (Ctrl+Shift+P → *Python: Select Interpreter*).

> Alternative to step 5: `mysql -u root -p < database/schema.sql`, then still run `python database/init_db.py` to create the officer and departments.

### Logging in
* **Officer:** the `OFFICER_EMAIL` / `OFFICER_PASSWORD` you set in `.env` (create it with `init_db.py`).
* **Students:** register on the *Student Register* page, or the officer adds them (a temporary password is shown once).
* With `--demo`: student `student@example.com` / `demo123` (plus four more demo students, same password).

---

## 4. Manual configuration (required)

These cannot be done for you – please check each one:

1. **`.env`** – copy from `.env.example` and set:
   * `DB_USER`, `DB_PASSWORD` (and `DB_HOST`/`DB_PORT` if not default) to match **your** MySQL.
   * `SECRET_KEY` – a long random string (`python -c "import secrets;print(secrets.token_hex(32))"`).
   * `OFFICER_EMAIL`, `OFFICER_PASSWORD`, `OFFICER_NAME` – the first officer account. **Change the password.**
   * `OFFICER_SIGNUP_CODE` – shared secret for the "create officer account" screen. Leave empty to **disable** officer self-creation.
2. **MySQL must be running** before `init_db.py` and `app.py`.
3. **Departments** default to CSE, ISE, ECE, MECH – edit them in *Officer → Settings*.
4. **Institution name / season** – *Officer → Settings* (appear in the PDF report).
5. **No email is sent.** "Forgot password" tells students to contact the officer, who issues a temporary password (*Students → Reset password*). Add SMTP yourself if you need email reset.

---

## 5. How the main workflow works

1. Student registers → logs in → completes profile → uploads PDF resume.
2. `POST /api/student/resume` validates the PDF, extracts text, runs the NLP analyser, stores file + analysis in MySQL; the **dashboard** and **resume page** read the stored analysis. "Add detected skills to my profile" merges them into the profile, which feeds skill-gap, eligibility and recommendations.
3. Officer adds companies and posts jobs with eligibility rules; eligible students are notified.
4. Student sees *Eligible / Not eligible* (with reasons) and applies. Deadline, duplicates and eligibility are re-checked **on the server**.
5. Officer reviews the resume, shortlists, schedules rounds (Technical/HR rounds move the status automatically; the student is notified), and finally selects / rejects. *Selected* writes a row to `placement_results`.
6. Student sees the result; officer sees results, reports, PDF and CSV downloads.

### Eligibility rules (mandatory)
`CGPA ≥ min_cgpa` **and** `backlogs ≤ max_backlogs` **and** department allowed (blank = all) **and** deadline not passed. Skill match is informational only.

### What the "AI / NLP" does (and doesn't)
* Pure-Python NLP – **no ML model or LLM** and nothing to download. A skill taxonomy with aliases (e.g. `postgres → PostgreSQL`, `js → JavaScript`) is matched with word-boundary-aware regex; resume sections/contacts are detected with pattern matching; the 100-point score is a transparent rubric (contact 10, summary 5, education 15, skills 25, projects 20, experience 5, certifications 5, links 5, impact verbs/metrics 6, length 4).
* Recommendations = **70 % skill overlap + 30 % TF-IDF cosine similarity** between the student's profile/resume text and the job text.
* Scanned/image-only PDFs have no text layer and are rejected with a clear message (no OCR included). Unusual multi-column layouts may reduce detection accuracy.
* The taxonomy is in `services/nlp.py` (`SKILLS`) – extend it for your departments.

---

## 6. Tests

```bash
# use a THROW-AWAY database name in .env (e.g. DB_NAME=placeiq_test) – tests create data
python database/init_db.py --reset
pytest -v
```
Covers registration/login/role protection, validation, PDF upload + analysis, eligibility rules, apply rules, shortlisting, interviews, selection, notifications, reports (PDF/CSV), password change, officer creation guard and cascade delete.

---

## 7. API overview (all JSON, session-cookie auth)

| Prefix | Notes |
|---|---|
| `/api/auth/*` | `register`, `login`, `logout`, `me`, `officer-register`, `change-password`, `notifications` |
| `/api/student/*` | `profile`, `resume`, `resume/file`, `resume/apply-skills`, `jobs`, `jobs/<id>`, `apply/<id>`, `skill-gap`, `recommendations`, `applications`, `interviews`, `results`, `dashboard` |
| `/api/officer/*` | `dashboard`, `students`, `companies`, `jobs`, `applications`, `interviews`, `results`, `reports/summary`, `reports/export.csv?type=applications\|students\|placements`, `reports/placement.pdf`, `settings`, `departments` |
| `/api/departments`, `/api/health` | public |

Student endpoints return 403 to officers and vice-versa.

---

## 8. Security notes
* Passwords hashed with Werkzeug (PBKDF2); login attempts rate-limited (in memory – resets on restart, per process).
* Session cookie is HttpOnly + SameSite=Lax. There are no separate CSRF tokens; this is adequate for an internal college deployment, but add CSRF protection if you expose it publicly.
* All SQL is parameterised; all user text is HTML-escaped in the UI; uploads are checked for `%PDF` signature, size limit (`MAX_RESUME_MB`) and stored under random names.
* For production: set `FLASK_DEBUG=0`, a strong `SECRET_KEY`, serve over HTTPS and run `gunicorn app:app` (Linux/macOS) or `waitress` on Windows behind a reverse proxy. Do not use the Flask dev server in production.

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to MySQL` | MySQL not running, or wrong `DB_*` values in `.env`. |
| `RuntimeError: 'cryptography' package is required` | `pip install -r requirements.txt` (it is listed; MySQL 8 needs it for `caching_sha2_password`). |
| `Access denied for user` | Fix `DB_USER` / `DB_PASSWORD`, or create a MySQL user with privileges. |
| Resume says "No readable text found" | The PDF is a scan/image. Export a text-based PDF from Word/Google Docs. |
| Port already in use | Change `PORT` in `.env`. |
| Reset everything | `python database/init_db.py --reset` (**deletes all data**; uploaded PDFs in `uploads/resumes/` must be deleted manually). |

---

## 10. Honest limitations
* Verified with Python 3.12 and **MariaDB 10.11** (MySQL-compatible). The SQL is standard and should run on MySQL 8, but it was not executed on a real MySQL 8 server here.
* UI behaviour was verified by running the real front-end JavaScript in a simulated DOM against the live server; it was **not** checked in a real browser. In particular the in-page PDF preview and the browser file-picker upload were not exercised in the UI test (the upload endpoint itself is tested over HTTP).
* No email, OCR, or ML/LLM-based analysis is included (see section 5).
* The officer "create account" screen uses a shared signup code from `.env`, not a per-user one-time code.
