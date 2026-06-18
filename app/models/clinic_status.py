from datetime import datetime

from app.extensions import db


class ClinicStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default="open")
    message = db.Column(db.String(255), nullable=False, default="Clinic is open.")
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    updater = db.relationship("User", backref="clinic_status_updates")

    def __repr__(self):
        return f"<ClinicStatus {self.status}>"
