from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import Scholarship, Application
from app.extensions import db
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import re
import os
import time

student_bp = Blueprint('student', __name__, template_folder='templates/student')

# ✅ allow these file types
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "doc", "docx"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def make_unique_filename(original_filename: str) -> str:
    # prevent overwrite by adding user_id + timestamp
    clean = secure_filename(original_filename)
    return f"{current_user.id}_{int(time.time())}_{clean}"


@student_bp.route('/dashboard')
@login_required
def dashboard():
    
    apps = Application.query.filter_by(student_id=current_user.id).all()
    return render_template('student/dashboard.html', applications=apps)


@student_bp.route('/scholarships')
@login_required
def scholarships():
    today = date.today()

    # ✅ Only show scholarships whose deadline is today or future
    scholarships = Scholarship.query.filter(
        Scholarship.application_deadline >= today
    ).all()

    for s in scholarships:
        c = s.eligibility_criteria
        req_lines = []

        if isinstance(c, dict):
            if c.get("min_cgpa") is not None:
                req_lines.append(f"Minimum CGPA: {c.get('min_cgpa')}")
            if c.get("max_income") is not None:
                req_lines.append(f"Maximum Household Income: RM{c.get('max_income')}")
            if c.get("required_criteria"):
                req_lines += [str(x) for x in c.get("required_criteria") if x]
        elif c:
            req_lines = [line.strip() for line in str(c).split("\n") if line.strip()]

        s.req_lines = req_lines

    return render_template('student/scholarships.html', scholarships=scholarships)


@student_bp.route('/apply/<int:scholarship_id>', methods=['GET', 'POST'])
@login_required
def apply(scholarship_id):
    scholarship = Scholarship.query.get_or_404(scholarship_id)

    
    UPLOAD_FOLDER = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    if request.method == 'POST':
        files_to_save = []

        # =========================
        # SAVE FILES (png/jpg/jpeg/pdf/doc/docx)
        # =========================

        # Passport photo
        photo = request.files.get('photo')
        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Photo file type not allowed. Allowed: png, jpg, jpeg, pdf, doc, docx", "danger")
                return redirect(request.url)

            photo_filename = make_unique_filename(photo.filename)
            photo.save(os.path.join(UPLOAD_FOLDER, photo_filename))
            files_to_save.append(f"uploads/{photo_filename}")

        # Academic document
        academic_doc = request.files.get('academic_doc')
        if academic_doc and academic_doc.filename:
            if not allowed_file(academic_doc.filename):
                flash("Document type not allowed. Allowed: png, jpg, jpeg, pdf, doc, docx", "danger")
                return redirect(request.url)

            doc_filename = make_unique_filename(academic_doc.filename)
            academic_doc.save(os.path.join(UPLOAD_FOLDER, doc_filename))
          
            files_to_save.append(f"uploads/{doc_filename}")

                # Income proof (PDF only)
        income_proof = request.files.get('income_proof')
        if income_proof and income_proof.filename:
            if not income_proof.filename.lower().endswith('.pdf'):
                flash("Income proof must be in PDF format.", "danger")
                return redirect(request.url)

            income_filename = make_unique_filename(income_proof.filename)
            income_proof.save(os.path.join(UPLOAD_FOLDER, income_filename))
            files_to_save.append(f"uploads/{income_filename}")

        # CGPA proof (PDF only)
        cgpa_proof = request.files.get('cgpa_proof')
        if cgpa_proof and cgpa_proof.filename:
            if not cgpa_proof.filename.lower().endswith('.pdf'):
                flash("CGPA proof must be in PDF format.", "danger")
                return redirect(request.url)

            cgpa_filename = make_unique_filename(cgpa_proof.filename)
            cgpa_proof.save(os.path.join(UPLOAD_FOLDER, cgpa_filename))
            files_to_save.append(f"uploads/{cgpa_filename}")


        # =========================
        # FORM DATA
        # =========================
        application_data = {
            "full_name": request.form.get('full_name'),
            "address": request.form.get('address'),
            "ic_number": request.form.get('ic_number'),
            "dob": request.form.get('dob'),
            "age": request.form.get('age'),
            "intake": request.form.get('intake'),
            "programme": request.form.get('programme'),
            "course": request.form.get('course'),
            "nationality": request.form.get('nationality'),
            "race": request.form.get('race'),
            "sex": request.form.get('sex'),
            "contact": request.form.get('contact'),
            "home_contact": request.form.get('home_contact'),
            "household_income": request.form.get('household_income'),
            "email": request.form.get('email'),
            "family_name": request.form.getlist('family_name[]'),
            "relationship": request.form.getlist('relationship[]'),
            "family_age": request.form.getlist('family_age[]'),
            "occupation": request.form.getlist('occupation[]'),
            "family_income": request.form.getlist('family_income[]'),
            "school_name": request.form.get('school_name'),
            "qualification": request.form.get('qualification'),
            "activity_type": request.form.getlist('activity_type[]'),
            "level": request.form.getlist('level[]'),
            "year": request.form.getlist('year[]'),
            "achievement": request.form.getlist('achievement[]'),
            "statement": request.form.get('statement')
        }

        # =========================
        # CREATE APPLICATION
        # =========================
        new_application = Application(
            student_id=current_user.id,
            scholarship_id=scholarship.id,
            documents=",".join(files_to_save),
            status="Pending",
            form_data=application_data
        )

        db.session.add(new_application)
        db.session.commit()

        flash("Your application has been submitted!", "success")
        return redirect(url_for('student.dashboard'))

    return render_template('student/apply.html', scholarship=scholarship)


@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        username = request.form.get('username')
        bio = request.form.get('bio')

        # Update username (bio 你如果 DB 没字段就不要写)
        current_user.username = username

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('student.profile'))

    return render_template('student/profile.html')


@student_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # 1. Check current password
        if not check_password_hash(current_user.password, current_password):
            flash("Current password is incorrect", "danger")
            return redirect(url_for('student.change_password'))

        # 2. Check new passwords match
        if new_password != confirm_password:
            flash("New passwords do not match", "danger")
            return redirect(url_for('student.change_password'))

        # 3. Password eligibility check
        if len(new_password) < 8 or not re.search(r"[A-Za-z]", new_password) or not re.search(r"\d", new_password):
            flash("Password must be at least 8 characters and contain letters and numbers", "danger")
            return redirect(url_for('student.change_password'))

        # 4. Update password
        current_user.password = generate_password_hash(new_password)
        db.session.commit()

        flash("Password updated successfully", "success")
        return redirect(url_for('student.profile'))

    return render_template('student/change_password.html')


@student_bp.route('/eligibility/<int:scholarship_id>', methods=['GET', 'POST'])
@login_required
def eligibility(scholarship_id):
    scholarship = Scholarship.query.get_or_404(scholarship_id)
    eligible = None

    if request.method == 'POST':
        # simple keyword match in profile
        criteria = scholarship.eligibility_criteria or ""
        if str(criteria).lower() in current_user.username.lower():
            eligible = True
        else:
            eligible = False

    return render_template('student/eligibility.html', scholarship=scholarship, eligible=eligible)
