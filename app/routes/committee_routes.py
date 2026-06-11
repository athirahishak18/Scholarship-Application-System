from flask import Blueprint, render_template, request, abort, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, case, or_, and_

from app.extensions import db
from app.models import Application, Review, SystemLog

# OPTIONAL: if you want to call your simulated notification function
# If your notifications.py currently uses Flask-Mail and may error (no mail config),
# we catch exceptions anyway.
try:
    from app.notifications import send_notification
except Exception:
    send_notification = None


committee_bp = Blueprint(
    "committee",
    __name__,
    template_folder="../templates/committee"
)


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
# DASHBOARD (NOW WITH NUMBERS)
# =========================
@committee_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "committee":
        abort(403)

    applications = Application.query.all()
    applications = Application.query.all()
    total = len(applications)

    accepted = sum(1 for a in applications if a.status == "Accepted")
    rejected = sum(1 for a in applications if a.status == "Rejected")

    # Everything else is Pending
    pending = total - accepted - rejected

    return render_template(
        "committee/dashboard.html",
        total=total,
        pending=pending,
        accepted=accepted,
        rejected=rejected
    )


# =========================
# APPLICATION LIST
# =========================
@committee_bp.route("/applications")
@login_required
def applications():
    if current_user.role != "committee":
        abort(403)

    status = request.args.get("status")
    sort = request.args.get("sort")
    fail_only = request.args.get("fail")

    # ✅ "Completed" = has a score (decision may be None)
    completed = Review.score.isnot(None)

    # --- aggregate review data per application ---
    agg = (
        db.session.query(
            Review.application_id.label("app_id"),

            # avg score only from rows that have a score
            func.avg(
                case((completed, Review.score), else_=None)
            ).label("avg_score"),

            # fail count: score<50 OR decision=="Fail" (only if score exists)
            func.sum(
                case(
                    (and_(completed, or_(Review.score < 50, Review.decision == "Fail")), 1),
                    else_=0
                )
            ).label("fail_count"),

            # count how many scored reviews exist
            func.sum(
                case((completed, 1), else_=0)
            ).label("scored_count")
        )
        .group_by(Review.application_id)
        .subquery()
    )

    # ✅ Do NOT coalesce avg_score to 0 (keep None => show N/A in UI)
    q = (
        db.session.query(
            Application,
            agg.c.avg_score.label("avg_score"),
            func.coalesce(agg.c.fail_count, 0).label("fail_count"),
            func.coalesce(agg.c.scored_count, 0).label("scored_count"),
        )
        .outerjoin(agg, agg.c.app_id == Application.id)
    )

    # --- status filter ---
    if status:
        if status == "Submitted":
            q = q.filter(
                or_(
                    Application.status.in_(["Submitted", "Pending", "Reviewed"]),
                    Application.status.is_(None),
                    Application.status == "None"
                )
            )
        elif status == "Reviewed":
            # ✅ Reviewed = has at least 1 score entered
            q = q.filter(func.coalesce(agg.c.scored_count, 0) > 0)
        else:
            q = q.filter(Application.status == status)

    # --- fail only ---
    if fail_only == "1":
        q = q.filter(func.coalesce(agg.c.fail_count, 0) > 0)

    # --- sorting ---
    if sort == "avg_score_asc":
        q = q.order_by(agg.c.avg_score.asc().nullslast())
    elif sort == "avg_score_desc":
        q = q.order_by(agg.c.avg_score.desc().nullslast())
    else:
        q = q.order_by(Application.id.desc())

    rows = q.all()
    return render_template("committee/applications.html", rows=rows)

# =========================
# VIEW SINGLE APPLICATION
# =========================
@committee_bp.route("/applications/<int:application_id>")
@login_required
def view_application(application_id):
    if current_user.role != "committee":
        abort(403)

    app_obj = Application.query.get_or_404(application_id)
    reviews = Review.query.filter_by(application_id=application_id).all()

    # ✅ only completed reviews counted
    scores = []
    for r in reviews:
        if r.decision is not None and r.score is not None:
            try:
                scores.append(float(r.score))
            except (TypeError, ValueError):
                pass

    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    # ✅ fail count only from completed reviews
    fail_count = sum(
        1 for r in reviews
        if (r.decision is not None and r.score is not None) and
           ((r.decision == "Fail") or (float(r.score) < 50))
    )

    return render_template(
        "committee/view_application.html",
        application=app_obj,
        reviews=reviews,
        avg_score=avg_score,
        fail_count=fail_count
    )


# =========================
# ACCEPT / REJECT + NOTIFY (SIMULATED)
# =========================
@committee_bp.route("/applications/<int:application_id>/decision/<string:decision>", methods=["POST"])
@login_required
def decide_application(application_id, decision):
    if current_user.role != "committee":
        abort(403)

    app_obj = Application.query.get_or_404(application_id)

    decision = decision.lower().strip()
    if decision not in ("accept", "reject"):
        abort(400)

    new_status = "Accepted" if decision == "accept" else "Rejected"
    app_obj.status = new_status
    db.session.commit()

    # log event (safe)
    log_event("info", "committee_decision", f"Application {app_obj.id} set to {new_status}", current_user.id)

    # notification (simulated)
    try:
        student_email = app_obj.student.email if app_obj.student else None
        if send_notification and student_email:
            send_notification(
                student_email,
                f"Scholarship Application {new_status}",
                f"Your application (ID {app_obj.id}) has been {new_status}."
            )
            flash(f"✅ Status updated to {new_status}. Email notification sent.", "success")
        else:
            flash(f"✅ Status updated to {new_status}. Notification simulated.", "success")
    except Exception:
        flash(f"✅ Status updated to {new_status}. Notification simulated (mail not configured).", "warning")

    return redirect(url_for("committee.view_application", application_id=application_id))
