import os
import sqlite3
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, g, render_template, request, redirect, url_for, session, jsonify
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from werkzeug.security import generate_password_hash, check_password_hash

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# In Docker, DATA_DIR points at a mounted volume so the database survives
# container rebuilds. Locally, it defaults to the project's data directory.
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(PROJECT_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "suggestions.db")

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_DIR, "templates"),
    static_folder=os.path.join(PROJECT_DIR, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# --- Config knobs -----------------------------------------------------
MIN_MESSAGE_LENGTH = 20
MAX_MESSAGE_LENGTH = 2000
RATE_LIMIT_WINDOW_MINUTES = 60
RATE_LIMIT_MAX_SUBMISSIONS = 3
CATEGORIES = ["Academics", "Facilities", "Bullying / Safety", "Teachers & Staff", "Events", "Other"]
CRUDE_WORD_FILTER = {"idiot", "stupid", "dumb", "hate you", "kill"}  # light heuristic flag, not a hard block

# --- Admin credentials --------------------------------------------------
# Staff accounts now live in the database (admin_users table) and are
# managed from the "Manage staff" page inside the admin panel — no terminal
# needed. A default account is seeded the first time the app runs:
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "dhruv@777"
PASSWORD_HASH_METHOD = "pbkdf2:sha256:600000"


def verify_password(password_hash: str, password: str) -> bool:
    """Verify current hashes and legacy scrypt hashes on Python without hashlib.scrypt."""
    if not password_hash.startswith("scrypt:") or hasattr(hashlib, "scrypt"):
        return check_password_hash(password_hash, password)

    method, salt, expected = password_hash.split("$")
    _, n, r, p = method.split(":")
    derived = Scrypt(
        salt=salt.encode(),
        length=64,
        n=int(n),
        r=int(r),
        p=int(p),
    ).derive(password.encode()).hex()
    return hmac.compare_digest(derived, expected)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            flagged INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        )
        """
    )
    # Ephemeral rate-limit table: only IP + timestamp, purged constantly, never shown to anyone
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS submission_log (
            ip_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'staff',
            created_at TEXT NOT NULL
        )
        """
    )
    # Migration: older databases created before roles existed won't have
    # this column yet — add it if missing.
    existing_cols = [row["name"] for row in db.execute("PRAGMA table_info(admin_users)").fetchall()]
    if "role" not in existing_cols:
        db.execute("ALTER TABLE admin_users ADD COLUMN role TEXT NOT NULL DEFAULT 'staff'")

    # Seed one default account the very first time the app is ever run.
    # This first account is the only one with the "admin" role until they
    # promote someone else — only admins can add/remove staff accounts.
    existing = db.execute("SELECT COUNT(*) as c FROM admin_users").fetchone()
    if existing["c"] == 0:
        db.execute(
            "INSERT INTO admin_users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
            (DEFAULT_ADMIN_USERNAME, generate_password_hash(DEFAULT_ADMIN_PASSWORD, method=PASSWORD_HASH_METHOD), datetime.utcnow().isoformat()),
        )
    else:
        # Migration for databases created before roles existed: if nobody
        # has the admin role yet, promote the earliest-created account.
        has_admin = db.execute("SELECT COUNT(*) as c FROM admin_users WHERE role = 'admin'").fetchone()["c"]
        if has_admin == 0:
            oldest = db.execute("SELECT id FROM admin_users ORDER BY created_at ASC LIMIT 1").fetchone()
            if oldest:
                db.execute("UPDATE admin_users SET role = 'admin' WHERE id = ?", (oldest["id"],))
    db.commit()
    db.close()


def hash_ip(ip: str) -> str:
    # one-way hash so we never store a raw, reversible IP address
    import hashlib
    salt = app.secret_key
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


def is_rate_limited(ip: str) -> bool:
    db = get_db()
    cutoff = (datetime.utcnow() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)).isoformat()
    ip_h = hash_ip(ip)
    # purge old rows opportunistically
    db.execute("DELETE FROM submission_log WHERE created_at < ?", (cutoff,))
    row = db.execute(
        "SELECT COUNT(*) as c FROM submission_log WHERE ip_hash = ? AND created_at >= ?",
        (ip_h, cutoff),
    ).fetchone()
    db.commit()
    return row["c"] >= RATE_LIMIT_MAX_SUBMISSIONS


def log_submission(ip: str):
    db = get_db()
    db.execute(
        "INSERT INTO submission_log (ip_hash, created_at) VALUES (?, ?)",
        (hash_ip(ip), datetime.utcnow().isoformat()),
    )
    db.commit()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


def admin_role_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        if session.get("admin_role") != "admin":
            return render_template("admin_forbidden.html"), 403
        return f(*args, **kwargs)
    return wrapper


# --- Public routes -------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or request.form
    category = (data.get("category") or "Other").strip()
    message = (data.get("message") or "").strip()
    honest_check = data.get("honest_check")

    if category not in CATEGORIES:
        category = "Other"

    errors = []
    if len(message) < MIN_MESSAGE_LENGTH:
        errors.append(f"Please write at least {MIN_MESSAGE_LENGTH} characters — give us enough to act on.")
    if len(message) > MAX_MESSAGE_LENGTH:
        errors.append("That note's too long — please keep it under 2000 characters.")
    if not honest_check:
        errors.append("Please confirm this is a genuine concern before sending.")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if not errors and is_rate_limited(ip):
        errors.append("Too many notes sent recently from this connection. Please try again later.")

    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    flagged = 1 if any(w in message.lower() for w in CRUDE_WORD_FILTER) else 0

    db = get_db()
    db.execute(
        "INSERT INTO suggestions (category, message, flagged, status, created_at) VALUES (?, ?, ?, 'new', ?)",
        (category, message, flagged, datetime.utcnow().isoformat()),
    )
    db.commit()
    log_submission(ip)

    return jsonify({"ok": True})


# --- Admin routes ----------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
        if user and verify_password(user["password_hash"], password):
            if user["password_hash"].startswith("scrypt:"):
                db.execute(
                    "UPDATE admin_users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(password, method=PASSWORD_HASH_METHOD), user["id"]),
                )
                db.commit()
            session["is_admin"] = True
            session["admin_id"] = user["id"]
            session["admin_username"] = user["username"]
            session["admin_role"] = user["role"]
            return redirect(url_for("admin_dashboard"))
        error = "Incorrect username or password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    status_filter = request.args.get("status", "all")
    query = "SELECT * FROM suggestions"
    params = ()
    if status_filter in ("new", "seen", "resolved", "spam"):
        query += " WHERE status = ?"
        params = (status_filter,)
    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()

    counts = {}
    for s in ("new", "seen", "resolved", "spam"):
        counts[s] = db.execute("SELECT COUNT(*) as c FROM suggestions WHERE status = ?", (s,)).fetchone()["c"]

    return render_template(
        "admin_dashboard.html",
        suggestions=rows,
        counts=counts,
        active_filter=status_filter,
        current_role=session.get("admin_role"),
    )


@app.route("/admin/update_status", methods=["POST"])
@login_required
def update_status():
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id")
    new_status = data.get("status")
    if new_status not in ("new", "seen", "resolved", "spam"):
        return jsonify({"ok": False, "error": "invalid status"}), 400
    db = get_db()
    db.execute("UPDATE suggestions SET status = ? WHERE id = ?", (new_status, suggestion_id))
    db.commit()
    return jsonify({"ok": True})


@app.route("/admin/delete_suggestion", methods=["POST"])
@login_required
def delete_suggestion():
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id")
    if not suggestion_id:
        return jsonify({"ok": False, "error": "Missing note id."}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    if not existing:
        return jsonify({"ok": False, "error": "That note no longer exists."}), 404

    db.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/admin/users", methods=["GET", "POST"])
@admin_role_required
def admin_users_page():
    db = get_db()
    add_error = None
    add_success = None

    if request.method == "POST" and request.form.get("form_name") == "add_user":
        new_username = request.form.get("new_username", "").strip()
        new_password = request.form.get("new_password", "")
        new_role = request.form.get("new_role", "staff")
        if new_role not in ("staff", "admin"):
            new_role = "staff"
        if not new_username or not new_password:
            add_error = "Please fill in both a username and password."
        elif len(new_password) < 8:
            add_error = "Password must be at least 8 characters."
        else:
            existing = db.execute("SELECT id FROM admin_users WHERE username = ?", (new_username,)).fetchone()
            if existing:
                add_error = "That username is already taken."
            else:
                db.execute(
                    "INSERT INTO admin_users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (new_username, generate_password_hash(new_password, method=PASSWORD_HASH_METHOD), new_role, datetime.utcnow().isoformat()),
                )
                db.commit()
                add_success = f'Staff account "{new_username}" created with {new_role} access.'

    users = db.execute("SELECT id, username, role, created_at FROM admin_users ORDER BY created_at ASC").fetchall()

    return render_template(
        "admin_users.html",
        users=users,
        add_error=add_error,
        add_success=add_success,
        current_user_id=session.get("admin_id"),
    )


@app.route("/admin/users/delete", methods=["POST"])
@admin_role_required
def admin_users_delete():
    data = request.get_json(silent=True) or {}
    user_id = data.get("id")

    if user_id == session.get("admin_id"):
        return jsonify({"ok": False, "error": "You can't remove your own account while logged in."}), 400

    db = get_db()
    target = db.execute("SELECT * FROM admin_users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        return jsonify({"ok": False, "error": "That account no longer exists."}), 404

    total = db.execute("SELECT COUNT(*) as c FROM admin_users").fetchone()["c"]
    if total <= 1:
        return jsonify({"ok": False, "error": "At least one staff account must remain."}), 400

    if target["role"] == "admin":
        admin_count = db.execute("SELECT COUNT(*) as c FROM admin_users WHERE role = 'admin'").fetchone()["c"]
        if admin_count <= 1:
            return jsonify({"ok": False, "error": "At least one admin account must remain."}), 400

    db.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/admin/change_password", methods=["GET", "POST"])
@login_required
def admin_change_password():
    error = None
    success = None
    db = get_db()

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        user = db.execute("SELECT * FROM admin_users WHERE id = ?", (session.get("admin_id"),)).fetchone()

        if not user or not check_password_hash(user["password_hash"], current_password):
            error = "Your current password is incorrect."
        elif len(new_password) < 8:
            error = "New password must be at least 8 characters."
        elif new_password != confirm_password:
            error = "New password and confirmation don't match."
        else:
            db.execute(
                "UPDATE admin_users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password, method=PASSWORD_HASH_METHOD), user["id"]),
            )
            db.commit()
            success = "Password updated."

    return render_template("admin_change_password.html", error=error, success=success)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5463)
