import os
import sqlite3
from flask import Flask
from app.extensions import db, login_manager
from app.models import User

from app.routes.auth_routes import auth_bp
from app.routes.student_routes import student_bp
from app.routes.reviewer_routes import reviewer_bp
from app.routes.committee_routes import committee_bp
from app.routes.admin_routes import admin_bp


def _count_rows(db_file: str) -> int:
    """Return number of rows in application table if possible, else 0."""
    try:
        con = sqlite3.connect(db_file)
        cur = con.cursor()

        # Try common table names
        for table in ("application", "applications", "Application"):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                n = cur.fetchone()[0]
                con.close()
                return int(n)
            except Exception:
                continue

        con.close()
        return 0
    except Exception:
        return 0


def _find_best_db(project_root: str, instance_db: str) -> str:
    """
    Pick the DB that most likely contains your real data.
    Priority:
      1) instance/scholarship.db if it exists AND has rows
      2) any other scholarship.db under the project that has rows
      3) instance/scholarship.db (even if empty) as fallback
    """
    candidates = []

    # 1) instance DB (preferred)
    if os.path.exists(instance_db):
        candidates.append(instance_db)

    # 2) find any other scholarship.db inside project (recursively)
    for root, _, files in os.walk(project_root):
        for f in files:
            if f.lower() == "scholarship.db":
                full = os.path.join(root, f)
                if full not in candidates:
                    candidates.append(full)

    # Choose the one with the most rows (best guess)
    best = instance_db
    best_rows = -1
    for c in candidates:
        rows = _count_rows(c)
        if rows > best_rows:
            best_rows = rows
            best = c

    return best


def create_app():
    app = Flask(__name__, template_folder="app/templates")

    # =====================
    # BASIC CONFIG
    # =====================
    app.config["SECRET_KEY"] = "digital-system"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # =====================
    # DATABASE (AUTO PICK)
    # =====================
    os.makedirs(app.instance_path, exist_ok=True)
    instance_db = os.path.join(app.instance_path, "scholarship.db")

    project_root = os.path.dirname(os.path.abspath(__file__))
    chosen_db = _find_best_db(project_root, instance_db)

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + chosen_db

    print("\n==============================")
    print("✅ USING DATABASE FILE:")
    print("   ", chosen_db)
    print("   ", "Application rows =", _count_rows(chosen_db))
    print("==============================\n")

    # =====================
    # INIT EXTENSIONS
    # =====================
    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # =====================
    # REGISTER BLUEPRINTS
    # =====================
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(reviewer_bp, url_prefix="/reviewer")
    app.register_blueprint(committee_bp, url_prefix="/committee")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # =====================
    # CREATE TABLES (SAFE)
    # =====================
    with app.app_context():
        db.create_all()

    # =====================
    # HOME ROUTE
    # =====================
    @app.route("/")
    def home():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.role == "student":
                return '<script>window.location.href="/student/dashboard"</script>'
            elif current_user.role == "reviewer":
                return '<script>window.location.href="/reviewer/dashboard"</script>'
            elif current_user.role == "committee":
                return '<script>window.location.href="/committee/dashboard"</script>'
            elif current_user.role == "admin":
                return '<script>window.location.href="/admin/dashboard"</script>'
        return '<script>window.location.href="/auth/login"</script>'

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
