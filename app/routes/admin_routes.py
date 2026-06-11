from flask import render_template, redirect, url_for, flash, request, Blueprint, Response
from flask_login import login_required, login_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func

import csv
import io

from app.models import db, Scholarship, User, Application, Review, SystemLog
from app.forms import (
    ScholarshipForm,
    RegistrationForm,         # kept (even if not used yet)
    AssignReviewersForm,
    ApplicationStatusForm
)

admin_bp = Blueprint('admin', __name__)


# =========================
# HELPER: LOG EVENTS
# =========================
def log_event(level: str, action: str, message: str, user_id=None):
    try:
        db.session.add(SystemLog(
            level=level,
            action=action,
            message=message,
            user_id=user_id
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


# =========================
# ADMIN LOGIN
# =========================
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if not user or user.role != 'admin':
            flash("Admin account not found.", "danger")
            return redirect(url_for('admin.admin_login'))

        if not check_password_hash(user.password, password):
            flash("Incorrect password.", "danger")
            return redirect(url_for('admin.admin_login'))

        login_user(user)
        flash("Welcome Admin!", "success")
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/login.html')


# =========================
# DASHBOARD
# =========================
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    total_apps = Application.query.count()
    total_scholarships = Scholarship.query.count()

    return render_template(
        'admin/dashboard.html',
        total_apps=total_apps,
        total_scholarships=total_scholarships
    )


# =========================
# CREATE SCHOLARSHIP (structured JSON)
# =========================
from datetime import date
from flask import flash, redirect, render_template, url_for
from flask_login import login_required, current_user

@admin_bp.route('/create_scholarship', methods=['GET', 'POST'])
@login_required
def create_scholarship():
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    form = ScholarshipForm()

    if form.validate_on_submit():
        criteria = {}

        if form.min_cgpa.data is not None:
            criteria["min_cgpa"] = float(form.min_cgpa.data)

        if form.max_income.data is not None:
            criteria["max_income"] = int(form.max_income.data)

        required_list = []
        if form.other_requirements.data:
            required_list = [
                line.strip()
                for line in form.other_requirements.data.split("\n")
                if line.strip()
            ]
        if required_list:
            criteria["required_criteria"] = required_list

        scholarship = Scholarship(
            title=form.title.data,
            description=form.description.data,
            eligibility_criteria=criteria if criteria else None,
            documents_required=form.documents_required.data,
            application_deadline=form.application_deadline.data
        )

        db.session.add(scholarship)
        db.session.commit()

        log_event(
            "info",
            "CREATE_SCHOLARSHIP",
            f"Admin created scholarship: {scholarship.title} (ID {scholarship.id})",
            user_id=current_user.id
        )

        flash("Scholarship created successfully!", "success")
        return redirect(url_for('admin.manage_scholarships'))


    return render_template('admin/create_scholarship.html', form=form, date=date)


# =========================
# MANAGE SCHOLARSHIPS (LIST)
# =========================
@admin_bp.route('/scholarships')
@login_required
def manage_scholarships():
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    scholarships = Scholarship.query.order_by(Scholarship.id.desc()).all()

    rows = (
        db.session.query(Application.scholarship_id, func.count(Application.id))
        .group_by(Application.scholarship_id)
        .all()
    )
    app_counts = {sid: cnt for sid, cnt in rows}

    return render_template(
        'admin/manage_scholarships.html',
        scholarships=scholarships,
        app_counts=app_counts
    )


# =========================
# SCHOLARSHIP DETAIL
# =========================
@admin_bp.route('/scholarships/<int:scholarship_id>')
@login_required
def scholarship_detail(scholarship_id):
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    scholarship = Scholarship.query.get_or_404(scholarship_id)
    application_count = Application.query.filter_by(scholarship_id=scholarship.id).count()

    criteria = scholarship.eligibility_criteria
    eligibility_lines = []

    if isinstance(criteria, dict):
        if criteria.get("min_cgpa") is not None:
            eligibility_lines.append(f"Minimum CGPA: {criteria.get('min_cgpa')}")
        if criteria.get("max_income") is not None:
            eligibility_lines.append(f"Maximum Household Income: RM{criteria.get('max_income')}")
        if criteria.get("required_criteria"):
            eligibility_lines.extend([str(x) for x in criteria.get("required_criteria")])
    elif criteria:
        eligibility_lines = [line.strip() for line in str(criteria).split("\n") if line.strip()]

    return render_template(
        'admin/scholarship_detail.html',
        scholarship=scholarship,
        application_count=application_count,
        eligibility_lines=eligibility_lines
    )


# =========================
# EDIT SCHOLARSHIP
# =========================
@admin_bp.route('/scholarships/<int:scholarship_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_scholarship(scholarship_id):
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    scholarship = Scholarship.query.get_or_404(scholarship_id)
    form = ScholarshipForm()

    if request.method == 'GET':
        form.title.data = scholarship.title
        form.description.data = scholarship.description or ""
        form.documents_required.data = scholarship.documents_required or ""

        if scholarship.application_deadline:
            try:
                form.application_deadline.data = scholarship.application_deadline
            except Exception:
                pass

        criteria = scholarship.eligibility_criteria
        if isinstance(criteria, dict):
            if "min_cgpa" in criteria:
                try:
                    form.min_cgpa.data = criteria.get("min_cgpa")
                except Exception:
                    pass
            if "max_income" in criteria:
                try:
                    form.max_income.data = criteria.get("max_income")
                except Exception:
                    pass
            if "required_criteria" in criteria and isinstance(criteria.get("required_criteria"), list):
                form.other_requirements.data = "\n".join([str(x) for x in criteria.get("required_criteria")])

    if form.validate_on_submit():
        criteria = {}

        if form.min_cgpa.data is not None:
            criteria["min_cgpa"] = float(form.min_cgpa.data)

        if form.max_income.data is not None:
            criteria["max_income"] = int(form.max_income.data)

        required_list = []
        if form.other_requirements.data:
            required_list = [line.strip() for line in form.other_requirements.data.split("\n") if line.strip()]
        if required_list:
            criteria["required_criteria"] = required_list

        scholarship.title = form.title.data
        scholarship.description = form.description.data
        scholarship.documents_required = form.documents_required.data
        scholarship.application_deadline = form.application_deadline.data
        scholarship.eligibility_criteria = criteria if criteria else None

        db.session.commit()

        log_event(
            "info",
            "EDIT_SCHOLARSHIP",
            f"Admin edited scholarship: {scholarship.title} (ID {scholarship.id})",
            user_id=current_user.id
        )

        flash("Scholarship updated successfully!", "success")
        return redirect(url_for('admin.scholarship_detail', scholarship_id=scholarship.id))

    return render_template('admin/edit_scholarship.html', form=form, scholarship=scholarship)


# =========================
# MANAGE USERS (CREATE + LIST)
# =========================
@admin_bp.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    # CREATE USER (POST)
    if request.method == 'POST':
        action = request.form.get("action", "").strip()

        if action == "create_user":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            role = request.form.get("role", "").strip()
            password = request.form.get("password", "").strip()

            if not username or not email or not role or not password:
                flash("Please fill in all fields.", "danger")
                return redirect(url_for('admin.manage_users'))

            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "danger")
                return redirect(url_for('admin.manage_users'))

            if User.query.filter_by(email=email).first():
                flash("Email already exists.", "danger")
                return redirect(url_for('admin.manage_users'))

            new_user = User(
                username=username,
                email=email,
                role=role,
                password=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()

            log_event(
                "info",
                "CREATE_USER",
                f"Admin created user: {username} ({role})",
                user_id=current_user.id
            )

            flash("User created successfully.", "success")
            return redirect(url_for('admin.manage_users'))

        flash("Invalid action.", "danger")
        return redirect(url_for('admin.manage_users'))

    # LIST USERS (GET)
    users = User.query.order_by(User.id.asc()).all()
    return render_template('admin/manage_users.html', users=users)


@admin_bp.route('/manage_users/<int:user_id>/edit', methods=['POST'])
@login_required
def edit_user(user_id):
    """
    ✅ Email is NOT editable.
    Admin can only edit: username, role, optional password reset.
    """
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(user_id)

    username = request.form.get("username", "").strip()
    role = request.form.get("role", "").strip()
    new_password = request.form.get("password", "").strip()

    if not username or not role:
        flash("Username and role are required.", "danger")
        return redirect(url_for("admin.manage_users"))

    if User.query.filter(User.username == username, User.id != user.id).first():
        flash("Username already used by another user.", "danger")
        return redirect(url_for("admin.manage_users"))

    user.username = username
    user.role = role

    # Optional password reset
    if new_password:
        user.password = generate_password_hash(new_password)

    db.session.commit()

    log_event(
        "info",
        "EDIT_USER",
        f"Admin edited user ID {user.id}: {username} ({role})",
        user_id=current_user.id
    )

    flash("User updated successfully.", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route('/manage_users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(user_id)

    # Safety: do not delete yourself
    if user.id == current_user.id:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for("admin.manage_users"))

    try:
        db.session.delete(user)
        db.session.commit()

        log_event(
            "warning",
            "DELETE_USER",
            f"Admin deleted user ID {user.id}: {user.username} ({user.role})",
            user_id=current_user.id
        )

        flash("User deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Delete failed. This user may be linked to applications/reviews.", "danger")

    return redirect(url_for("admin.manage_users"))


# =========================
# MANAGE APPLICATIONS
# =========================
@admin_bp.route('/applications')
@login_required
def manage_applications():
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    applications = Application.query.order_by(Application.id.desc()).all()

    forms = {}
    for a in applications:
        f = ApplicationStatusForm()
        f.status.data = a.status if hasattr(a, "status") and a.status else "Submitted"
        forms[a.id] = f

    return render_template('admin/manage_applications.html', applications=applications, forms=forms)


@admin_bp.route('/applications/<int:application_id>')
@login_required
def application_detail(application_id):
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    application = Application.query.get_or_404(application_id)

    documents = []
    if application.documents:
        documents = [d.strip() for d in application.documents.split(",") if d.strip()]

    return render_template(
        'admin/application_detail.html',
        application=application,
        documents=documents
    )


@admin_bp.route('/applications/<int:application_id>/status', methods=['POST'])
@login_required
def update_application_status(application_id):
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    app_obj = Application.query.get_or_404(application_id)
    form = ApplicationStatusForm()

    if form.validate_on_submit():
        app_obj.status = form.status.data
        db.session.commit()
        flash("Application status updated.", "success")
    else:
        flash("Failed to update status.", "danger")

    return redirect(url_for('admin.manage_applications'))


@admin_bp.route("/assign_reviewers/<int:application_id>", methods=["GET", "POST"])
@login_required
def assign_reviewers(application_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    application = Application.query.get_or_404(application_id)
    reviewers = User.query.filter_by(role="reviewer").all()

    form = AssignReviewersForm()
    form.reviewers.choices = [(r.id, r.username) for r in reviewers]

    if form.validate_on_submit():
        selected_ids = form.reviewers.data
        added = 0
        for reviewer_id in selected_ids:
            exists = Review.query.filter_by(application_id=application.id, reviewer_id=reviewer_id).first()
            if not exists:
                db.session.add(Review(application_id=application.id, reviewer_id=reviewer_id))
                added += 1

        db.session.commit()
        flash(f"Reviewers assigned successfully! Added {added}.", "success")
        return redirect(url_for("admin.manage_applications"))

    existing_reviews = Review.query.filter_by(application_id=application.id).all()
    assigned_reviewer_ids = {r.reviewer_id for r in existing_reviews}

    return render_template(
        "admin/assign_reviewers.html",
        application=application,
        form=form,
        reviewers=reviewers,
        assigned_reviewer_ids=assigned_reviewer_ids
    )


# =========================
# REPORTS (FIXED role_counts)
# =========================
@admin_bp.route("/reports")
@login_required
def reports():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    total_users = User.query.count()
    total_scholarships = Scholarship.query.count()
    total_apps = Application.query.count()

    status_rows = (
        db.session.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )
    status_counts = {status or "Unknown": count for status, count in status_rows}

    role_rows = (
        db.session.query(User.role, func.count(User.id))
        .group_by(User.role)
        .all()
    )
    role_counts = {role or "Unknown": count for role, count in role_rows}

    return render_template(
        "admin/reports.html",
        total_users=total_users,
        total_scholarships=total_scholarships,
        total_apps=total_apps,
        status_counts=status_counts,
        role_counts=role_counts
    )


# =========================
# EXPORT REPORT CSV
# =========================
@admin_bp.route("/reports/export.csv")
@login_required
def export_reports_csv():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Users", User.query.count()])
    writer.writerow(["Total Scholarships", Scholarship.query.count()])
    writer.writerow(["Total Applications", Application.query.count()])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=reports.csv"}
    )


# =========================
# SYSTEM LOGS
# =========================
@admin_bp.route("/logs")
@login_required
def system_logs():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(200).all()
    return render_template("admin/logs.html", logs=logs)

# =========================
# CLEAR LOGS
# =========================
@admin_bp.route("/logs/clear", methods=["POST"])
@login_required
def clear_logs():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    try:
        deleted = db.session.query(SystemLog).delete()
        db.session.commit()
        flash(f"Cleared {deleted} logs.", "success")

        log_event("warning", "CLEAR_LOGS", f"Admin cleared {deleted} logs.", user_id=current_user.id)

    except Exception:
        db.session.rollback()
        flash("Failed to clear logs.", "danger")

    return redirect(url_for("admin.system_logs"))
