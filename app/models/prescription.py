from datetime import datetime

from app.extensions import db


class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(
        db.Integer,
        db.ForeignKey("appointment.id"),
        nullable=False,
        unique=True,
    )
    patient_name = db.Column(db.String(100), nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    medicines = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    next_visit_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    pdf_filename = db.Column(db.String(255), nullable=True)
    qr_filename = db.Column(db.String(255), nullable=True)

    appointment = db.relationship(
        "Appointment",
        back_populates="prescription",
        uselist=False,
    )

    def __repr__(self):
        return f"<Prescription {self.id} - Appointment {self.appointment_id}>"
