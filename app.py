import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, g, abort
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

# --- الإعدادات (تتحكم فيها من المتغيرات البيئية على Railway) ---
# أسماء العروسين والعنوان اللي يطلع فوق الصفحة
COUPLE_NAME = os.environ.get("COUPLE_NAME", "سالم & نورة")
EVENT_TITLE = os.environ.get("EVENT_TITLE", "كلمات الأحبّة")
EVENT_SUBTITLE = os.environ.get("EVENT_SUBTITLE", "اكتب كلمة تبقى ذكرى")

# كلمة مرور صفحة الإدارة /admin
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")

# مجلد حفظ قاعدة البيانات (خله يشير لـ volume على Railway حتى ما تنمسح الرسائل)
DATA_DIR = os.environ.get("DATA_DIR", ".")
DB_PATH = os.path.join(DATA_DIR, "messages.db")


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def config():
    return dict(
        couple=COUPLE_NAME,
        title=EVENT_TITLE,
        subtitle=EVENT_SUBTITLE,
    )


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        message = (request.form.get("message") or "").strip()

        if not name or not message:
            return render_template(
                "index.html",
                error="اكتب اسمك وكلمتك قبل الإرسال",
                name=name,
                message=message,
                **config(),
            )

        db = get_db()
        db.execute(
            "INSERT INTO messages (name, message, created_at) VALUES (?, ?, ?)",
            (name[:80], message[:1000], datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
        return render_template("thanks.html", name=name, **config())

    return render_template("index.html", **config())


# ---------- صفحة الإدارة ----------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if (request.form.get("password") or "") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        error = "كلمة المرور غير صحيحة"
    return render_template("admin_login.html", error=error, **config())


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin():
    db = get_db()
    rows = db.execute(
        "SELECT id, name, message, created_at FROM messages ORDER BY id DESC"
    ).fetchall()
    return render_template("admin.html", messages=rows, count=len(rows), **config())


@app.route("/admin/delete/<int:msg_id>", methods=["POST"])
@login_required
def delete_message(msg_id):
    db = get_db()
    db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    db.commit()
    return redirect(url_for("admin"))


# جهّز قاعدة البيانات عند الإقلاع (يشتغل مع gunicorn و flask run)
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
