from app.extensions import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON


# =========================
# USER
# =========================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    your_id = db.Column(db.String(20), unique=True, nullable=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# SCHOLARSHIP
# =========================
class Scholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    eligibility_criteria = db.Column(db.JSON)
    application_deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    documents_required = db.Column(db.Text)  # comma-separated list


# =========================
# APPLICATION
# =========================
class Application(db.Model):
    __tablename__ = 'application'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'), nullable=False)

    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    documents = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship('Review', backref='application', lazy=True)
    scholarship = db.relationship('Scholarship', backref='applications')
    student = db.relationship('User', foreign_keys=[student_id], backref='applications')

    form_data = db.Column(JSON)


# =========================
# REVIEW
# =========================
class Review(db.Model):
    __tablename__ = 'review'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    score = db.Column(db.Integer)
    decision = db.Column(db.String(20))
    comment = db.Column(db.Text)

    comments = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship('User', backref='reviews')


# =========================
# SYSTEM LOGS
# =========================
class SystemLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    level = db.Column(db.String(20), default="info", nullable=False)
    action = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="system_logs", lazy=True)
