"""Authentication: student registration/login, officer login/creation, session helpers."""
import re
import time
from functools import wraps
from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from pymysql.err import IntegrityError

from config import Config
from db import query, one, execute, transaction
from services.core import notify

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")
USN_RE = re.compile(r"^[0-9][A-Za-z]{2}\d{2}[A-Za-z]{2,3}\d{3}$")
OPID_RE = re.compile(r"^OP-\d{4}-\d{2}$")

_attempts = {}  # ip/email -> [timestamps]  (simple in-memory brute-force guard)


def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


def body():
    return request.get_json(silent=True) or {}


def too_many(key):
    now = time.time()
    hits = [t for t in _attempts.get(key, []) if now - t < 300]
    _attempts[key] = hits
    return len(hits) >= 8


def record_fail(key):
    _attempts.setdefault(key, []).append(time.time())


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return one("SELECT id, name, email, role, designation, active FROM users WHERE id=%s", (uid,))


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u or not u["active"]:
                session.clear()
                return err("Please log in.", 401)
            if role and u["role"] != role:
                return err("You do not have access to this resource.", 403)
            request.user = u
            return fn(*a, **kw)
        return wrapper
    return deco


def user_payload(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"], "designation": u.get("designation")}


def password_problem(pw, minlen):
    if not pw or len(pw) < minlen:
        return "Password must be at least %d characters." % minlen
    return None


@bp.get("/me")
def me():
    u = current_user()
    if not u:
        return jsonify({"ok": True, "user": None})
    unread = one("SELECT COUNT(*) c FROM notifications WHERE user_id=%s AND is_read=0", (u["id"],))["c"]
    return jsonify({"ok": True, "user": user_payload(u), "unread": unread})


@bp.post("/register")
def register():
    d = body()
    name, usn, email = (d.get("name") or "").strip(), (d.get("usn") or "").strip().upper(), (d.get("email") or "").strip().lower()
    pw, dept = d.get("password") or "", (d.get("dept") or "").strip()
    year = d.get("year_of_study")
    if len(name) < 3:
        return err("Name is too short.")
    if not USN_RE.match(usn):
        return err("USN format should look like 1XX22CS014.")
    if not EMAIL_RE.match(email):
        return err("Enter a valid email address.")
    p = password_problem(pw, 6)
    if p:
        return err(p)
    if pw != d.get("confirm"):
        return err("Passwords do not match.")
    if not one("SELECT id FROM departments WHERE name=%s", (dept,)):
        return err("Select a valid department.")
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'student')",
                            (name, email, generate_password_hash(pw)))
                uid = cur.lastrowid
                cur.execute("INSERT INTO students (user_id,usn,dept,year_of_study) VALUES (%s,%s,%s,%s)",
                            (uid, usn, dept, int(year) if str(year or "").isdigit() else None))
        notify(uid, "Welcome to PlaceIQ! Complete your academic profile and upload your resume.")
    except IntegrityError as e:
        msg = str(e).lower()
        return err("This USN is already registered." if "usn" in msg else "This email is already registered.", 409)
    return jsonify({"ok": True, "message": "Registered successfully. Please log in."})


@bp.post("/login")
def login():
    d = body()
    email, pw, role = (d.get("email") or "").strip().lower(), d.get("password") or "", d.get("role")
    key = "%s|%s" % (request.remote_addr, email)
    if too_many(key):
        return err("Too many failed attempts. Try again in a few minutes.", 429)
    u = one("SELECT * FROM users WHERE email=%s", (email,))
    if not u or not check_password_hash(u["password_hash"], pw) or not u["active"] or (role and u["role"] != role):
        record_fail(key)
        return err("Invalid %s credentials." % (role or "login"), 401)
    session.clear()
    session["uid"] = u["id"]
    session.permanent = True
    unread = one("SELECT COUNT(*) c FROM notifications WHERE user_id=%s AND is_read=0", (u["id"],))["c"]
    return jsonify({"ok": True, "user": user_payload(u), "unread": unread})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.post("/officer-register")
def officer_register():
    """Create an additional officer account. Requires operator id + the server-side signup code."""
    d = body()
    if not Config.OFFICER_SIGNUP_CODE:
        return err("Officer self-creation is disabled. Set OFFICER_SIGNUP_CODE in .env to enable it.", 403)
    key = "officer|%s" % request.remote_addr
    if too_many(key):
        return err("Too many attempts. Try again later.", 429)
    if not OPID_RE.match((d.get("operator_id") or "").strip()) or (d.get("code") or "") != Config.OFFICER_SIGNUP_CODE:
        record_fail(key)
        return err("Operator ID or one-time code is invalid.", 403)
    name, email = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    if len(name) < 3 or not EMAIL_RE.match(email):
        return err("Enter a valid name and work email.")
    p = password_problem(pw, 8)
    if p:
        return err(p)
    if pw != d.get("confirm"):
        return err("Passwords do not match.")
    try:
        execute("INSERT INTO users (name,email,password_hash,role,designation) VALUES (%s,%s,%s,'officer',%s)",
                (name, email, generate_password_hash(pw), (d.get("designation") or "Placement Officer").strip()[:120]))
    except IntegrityError:
        return err("This email is already registered.", 409)
    return jsonify({"ok": True, "message": "Officer account created. You can log in now."})


@bp.post("/change-password")
@login_required()
def change_password():
    d = body()
    u = one("SELECT * FROM users WHERE id=%s", (request.user["id"],))
    if not check_password_hash(u["password_hash"], d.get("current") or ""):
        return err("Current password is incorrect.", 403)
    p = password_problem(d.get("new"), 8 if u["role"] == "officer" else 6)
    if p:
        return err(p)
    execute("UPDATE users SET password_hash=%s WHERE id=%s", (generate_password_hash(d["new"]), u["id"]))
    return jsonify({"ok": True, "message": "Password updated."})


@bp.get("/notifications")
@login_required()
def notifications():
    rows = query("SELECT id, message, is_read, created_at FROM notifications WHERE user_id=%s ORDER BY id DESC LIMIT 40",
                 (request.user["id"],))
    return jsonify({"ok": True, "items": [{"id": r["id"], "message": r["message"], "read": bool(r["is_read"]),
                                            "at": r["created_at"].strftime("%d %b %H:%M")} for r in rows]})


@bp.post("/notifications/read")
@login_required()
def notifications_read():
    execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (request.user["id"],))
    return jsonify({"ok": True})
