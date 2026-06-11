from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Application, Review

reviewer_bp = Blueprint(
    "reviewer",
    __name__,
    template_folder="templates/reviewer"
)

def reviewer_only():
    if current_user.role != "reviewer":
        abort(403)

# =========================
# DASHBOARD
# =========================
@reviewer_bp.route("/dashboard")
@login_required
def dashboard():
    reviewer_only()

    reviews = Review.query.filter_by(reviewer_id=current_user.id).all()

    total = len(reviews)

    # pending = not decided yet (matches main's "status/decision" workflow)
    pending = sum(1 for r in reviews if r.decision is None)
    reviewed = total - pending

    return render_template(
        "reviewer/dashboard.html",
        reviews=reviews,
        total=total,
        pending=pending,
        reviewed=reviewed
    )

# =========================
# VIEW ASSIGNED APPLICATIONS
# =========================
@reviewer_bp.route("/applications")
@login_required
def applications_list():
    reviewer_only()

    sort = request.args.get("sort")

    reviews = Review.query.filter_by(reviewer_id=current_user.id).join(Application).all()

    if sort == "date":
        reviews.sort(key=lambda r: r.application.submitted_at, reverse=True)
    elif sort == "status":
        reviews.sort(key=lambda r: (r.decision or ""))

    return render_template(
        "reviewer/dashboard.html",
        reviews=reviews
    )

# =========================
# REVIEW FORM
# =========================
@reviewer_bp.route("/review/<int:app_id>", methods=["GET", "POST"])
@login_required
def review(app_id):
    reviewer_only()

    app_obj = Application.query.get_or_404(app_id)

    review_row = Review.query.filter_by(
        application_id=app_obj.id,
        reviewer_id=current_user.id
    ).first_or_404()

    # Build data dict for template (avoid crash)
    application_data = {
        "full_name": app_obj.student.username if getattr(app_obj, "student", None) else "",
        "email": app_obj.student.email if getattr(app_obj, "student", None) else "",
        "ic_number": getattr(app_obj, "ic_number", ""),
        "dob": getattr(app_obj, "dob", ""),
        "age": getattr(app_obj, "age", ""),
        "address": getattr(app_obj, "address", ""),
        "intake": getattr(app_obj, "intake", ""),
        "programme": getattr(app_obj, "programme", ""),
        "course": getattr(app_obj, "course", ""),
        "nationality": getattr(app_obj, "nationality", ""),
        "race": getattr(app_obj, "race", ""),
        "sex": getattr(app_obj, "sex", ""),
        "contact": getattr(app_obj, "contact", ""),
        "home_contact": getattr(app_obj, "home_contact", ""),
        "household_income": getattr(app_obj, "household_income", ""),

        # arrays — prevent template crash
        "family_name": [],
        "relationship": [],
        "family_age": [],
        "occupation": [],
        "family_income": [],

        "activity_type": [],
        "level": [],
        "year": [],
        "achievement": [],

        "school_name": getattr(app_obj, "school_name", ""),
        "qualification": getattr(app_obj, "qualification", ""),
        "statement": getattr(app_obj, "statement", "")
    }

    if request.method == "POST":
        # score (safe)
        score_raw = request.form.get("score", "").strip()
        try:
            review_row.score = int(score_raw) if score_raw else None
        except ValueError:
            review_row.score = None

        # comment
        review_row.comment = request.form.get("comment")

        # IMPORTANT: main branch uses form field name "status"
        # (example values: "Pass"/"Fail"/"Reviewed" etc depending on your form)
        status_val = request.form.get("status")
        if status_val:
            review_row.decision = status_val
            app_obj.status = status_val
        else:
            # fallback if no status provided
            app_obj.status = "Reviewed"

        db.session.commit()
        flash("Review submitted successfully", "success")
        return redirect(url_for("reviewer.dashboard"))

    return render_template(
        "reviewer/reviewer.html",
        application=app_obj,
        review=review_row,
        application_data=application_data
    )

# =========================
# VIEW REVIEW
# =========================
@reviewer_bp.route("/review/<int:app_id>/view")
@login_required
def view_review(app_id):
    reviewer_only()

    review_row = Review.query.filter_by(
        application_id=app_id,
        reviewer_id=current_user.id
    ).first()

    if not review_row:
        flash("This application is not assigned to you.", "danger")
        return redirect(url_for("reviewer.applications_list"))

    return render_template(
        "reviewer/view_review.html",
        app=review_row.application,
        review=review_row
    )

# =========================
# RANKING
# =========================
@reviewer_bp.route("/ranking")
@login_required
def ranking():
    reviewer_only()

    reviews = Review.query.filter_by(reviewer_id=current_user.id).order_by(Review.score.desc()).all()

    return render_template(
        "reviewer/ranking.html",
        reviews=reviews
    )
