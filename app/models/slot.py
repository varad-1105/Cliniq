from datetime import datetime

from app.extensions import db


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_date = db.Column(db.Date, nullable=False)
    slot_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="available")
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Slot {self.slot_date} {self.slot_time} - {self.status}>"
