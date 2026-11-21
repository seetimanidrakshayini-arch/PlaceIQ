"""
Create the PlaceIQ database, tables, default departments and the default officer account.

    python database/init_db.py            # schema + departments + officer
    python database/init_db.py --demo     # also load the prototype's demo students/companies/jobs
    python database/init_db.py --reset    # DROP the database first (destroys all data!)
"""
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from werkzeug.security import generate_password_hash
from config import Config
from db import connect

DEMO_PASSWORD = "demo123"


def run_schema(conn):
    sql = open(os.path.join(os.path.dirname(__file__), "schema.sql"), encoding="utf-8").read()
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"(?im)^\s*(CREATE DATABASE|USE)\b[^;]*;", "", sql)
    with conn.cursor() as cur:
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            cur.execute(stmt)


def seed_base(conn):
    with conn.cursor() as cur:
        for d in ("CSE", "ISE", "ECE", "MECH"):
            cur.execute("INSERT IGNORE INTO departments (name) VALUES (%s)", (d,))
        cur.execute("INSERT IGNORE INTO settings (k,v) VALUES ('institution','Sample Institute of Technology'),('season','2026-27')")
        cur.execute("SELECT id FROM users WHERE email=%s", (Config.OFFICER_EMAIL.lower(),))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (name,email,password_hash,role,designation) VALUES (%s,%s,%s,'officer','Placement Officer')",
                        (Config.OFFICER_NAME, Config.OFFICER_EMAIL.lower(), generate_password_hash(Config.OFFICER_PASSWORD)))
            print("Created officer account:", Config.OFFICER_EMAIL)
        else:
            print("Officer account already exists:", Config.OFFICER_EMAIL)


def seed_demo(conn):
    """Same sample data as the original prototype, now stored in MySQL."""
    today = date.today()
    d = lambda n: (today + timedelta(days=n)).isoformat()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) c FROM companies")
        if cur.fetchone()["c"]:
            print("Demo data skipped (companies already exist).")
            return
        students = [
            ("Aarav Sharma", "student@example.com", "1XX22CS014", "CSE", 6, 2026, 8.2, 0,
             "Python, C++, MySQL, HTML, CSS", "Python, C++, SQL", "NPTEL Python for Everybody", "Library Management System; Weather App"),
            ("Diya Patel", "diya@example.com", "1XX22IS021", "ISE", 6, 2026, 9.1, 0, "Java, SQL, HTML", "Java, SQL", "", ""),
            ("Rohan Gupta", "rohan@example.com", "1XX22EC008", "ECE", 6, 2026, 7.4, 1, "C, Embedded, MATLAB", "C", "", ""),
            ("Sneha Iyer", "sneha@example.com", "1XX22CS031", "CSE", 6, 2026, 8.8, 0, "Python, JavaScript, MySQL, Flask", "Python, JavaScript", "", ""),
            ("Karan Mehta", "karan@example.com", "1XX22ME017", "MECH", 6, 2026, 6.8, 2, "AutoCAD, SolidWorks", "", "", ""),
        ]
        sid = []
        for n, e, usn, dept, sem, yr, cg, bl, sk, lg, ce, pr in students:
            cur.execute("INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'student')", (n, e, generate_password_hash(DEMO_PASSWORD)))
            uid = cur.lastrowid
            cur.execute("INSERT INTO students (user_id,usn,dept,semester,grad_year,year_of_study,cgpa,backlogs,skills,languages,certifications,projects) "
                        "VALUES (%s,%s,%s,%s,%s,3,%s,%s,%s,%s,%s,%s)", (uid, usn, dept, sem, yr, cg, bl, sk, lg, ce, pr))
            sid.append(cur.lastrowid)
        cos = [("TechNova", "Software", "technova.example"), ("DataWiz", "Analytics", "datawiz.example"),
               ("CloudSpan", "Cloud", "cloudspan.example"), ("FinEdge", "Fintech", "finedge.example"),
               ("InfraCore", "Infrastructure", "infracore.example")]
        cid = []
        for c in cos:
            cur.execute("INSERT INTO companies (name,industry,website) VALUES (%s,%s,%s)", c)
            cid.append(cur.lastrowid)
        jobs = [(0, "Software Engineer", 8.5, 7.5, 0, "Python, Data Structures, Flask, MySQL", 14, "Build and maintain backend services in Python."),
                (1, "Data Analyst", 6.5, 7, 1, "Python, SQL, Excel, Statistics", 9, "Analyse business data and build dashboards."),
                (2, "Backend Developer", 10, 8.5, 0, "JavaScript, Flask, Docker, MySQL", 25, "Design REST APIs and deploy containerised services."),
                (3, "Web Developer", 5.5, 6.5, 2, "HTML, CSS, JavaScript, React", 19, "Create responsive web interfaces."),
                (4, "Systems Engineer", 7, 8, 0, "C++, Linux, Data Structures", 34, "Develop and support Linux-based infrastructure software.")]
        jid = []
        for ci, role, pkg, cg, bl, sk, dl, desc in jobs:
            cur.execute("INSERT INTO jobs (company_id,role,description,package_lpa,min_cgpa,max_backlogs,skills,deadline) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (cid[ci], role, desc, pkg, cg, bl, sk, d(dl)))
            jid.append(cur.lastrowid)
        # (job idx, student idx, status)
        for ji, si, st in [(1, 0, "Technical Interview"), (3, 0, "Shortlisted"), (0, 1, "Applied"), (2, 3, "Under Review"), (0, 0, "Under Review")]:
            cur.execute("INSERT INTO applications (job_id,student_id,status) VALUES (%s,%s,%s)", (jid[ji], sid[si], st))
            if (ji, si) == (1, 0):
                cur.execute("INSERT INTO interviews (application_id,round_name,scheduled_date,scheduled_time,venue) VALUES (%s,'Technical Round',%s,'10:00','Seminar Hall A')",
                            (cur.lastrowid, d(2)))
        print("Demo data loaded. Demo student: student@example.com / %s" % DEMO_PASSWORD)


def main():
    reset, demo = "--reset" in sys.argv, "--demo" in sys.argv
    try:
        root = connect(database=False)
    except pymysql.MySQLError as e:
        sys.exit("Cannot connect to MySQL: %s\nCheck DB_HOST / DB_USER / DB_PASSWORD in your .env file and make sure MySQL is running." % e)
    with root.cursor() as cur:
        if reset:
            cur.execute("DROP DATABASE IF EXISTS `%s`" % Config.DB_NAME)
            print("Dropped database", Config.DB_NAME)
        cur.execute("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" % Config.DB_NAME)
    root.close()
    conn = connect()
    run_schema(conn)
    print("Schema ready in database '%s'." % Config.DB_NAME)
    seed_base(conn)
    if demo:
        seed_demo(conn)
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
