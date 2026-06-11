from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User
from app.extensions import db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        your_id = request.form.get("your_id")
        role = request.form.get("role")
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")

        # Password mismatch
        if password1 != password2:
            return render_template(
                "auth/register.html",
                current_user=current_user,
                error="Passwords do not match."
            )

        hashed_password = generate_password_hash(password1, method="scrypt")

        new_user = User(
            email=email,
            username=username,
            your_id=your_id,
            password=hashed_password,
            role=role
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            return render_template(
                "auth/register.html",
                current_user=current_user,
                success="Account successfully created! Please login."
            )
        except IntegrityError:
            db.session.rollback()
            return render_template(
                "auth/register.html",
                current_user=current_user,
                error="Email, username, or ID already exists."
            )

    return render_template("auth/register.html", current_user=current_user)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)

            # Handle "next" redirect after login
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)

            # Otherwise redirect based on role
            if user.role == 'student':
                return redirect(url_for('student.dashboard'))
            elif user.role == 'reviewer':
                return redirect(url_for('reviewer.dashboard'))
            elif user.role == 'committee':
                return redirect(url_for('committee.dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin.dashboard'))

            # fallback if role is unexpected
            
            return redirect(url_for('auth.login'))

        flash("Invalid credentials", "danger")
        return render_template('auth/login.html')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    role = current_user.role  # save role BEFORE logout_user()
    logout_user()
    flash("Logged out", "danger")

    # admin should go back to /admin/login
    if role == "admin":
        return redirect(url_for('admin.admin_login'))

    # everyone else goes to /auth/login
    return redirect(url_for('auth.login'))