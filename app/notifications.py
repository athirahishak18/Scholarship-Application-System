from flask_mail import Message
from app import mail

def send_notification(user_email, subject, body):
    msg = Message(subject, recipients=[user_email], body=body)
    mail.send(msg)
