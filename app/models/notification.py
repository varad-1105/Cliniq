from datetime import datetime

from app.extensions import db


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=True)
    patient_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="simulated")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    appointment = db.relationship("Appointment", backref="notifications")

    def __repr__(self):
        return f"<Notification {self.notification_type} - {self.status}>"
