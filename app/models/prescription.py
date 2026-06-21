import json
import secrets
from datetime import datetime

from sqlalchemy import inspect

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
    patient_age = db.Column(db.String(20), nullable=True)
    patient_gender = db.Column(db.String(30), nullable=True)
    doctor_name = db.Column(db.String(100), nullable=True)
    doctor_qualification = db.Column(db.String(120), nullable=True)
    doctor_specialization = db.Column(db.String(120), nullable=True)
    doctor_registration_number = db.Column(db.String(80), nullable=True)
    patient_history_summary = db.Column(db.Text, nullable=True)
    bp = db.Column(db.String(30), nullable=True)
    weight = db.Column(db.String(30), nullable=True)
    pulse = db.Column(db.String(30), nullable=True)
    spo2 = db.Column(db.String(30), nullable=True)
    diagnosis = db.Column(db.Text, nullable=False)
    medicines = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    lifestyle_advice = db.Column(db.Text, nullable=True)
    precautions = db.Column(db.Text, nullable=True)
    follow_up_notes = db.Column(db.Text, nullable=True)
    follow_up_recommendation = db.Column(db.Text, nullable=True)
    next_visit_date = db.Column(db.Date, nullable=True)
    access_token = db.Column(db.String(128), nullable=True, unique=True)
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

    @property
    def medicine_rows(self):
        if not self.medicines:
            return []

        try:
            rows = json.loads(self.medicines)
        except json.JSONDecodeError:
            return [
                {
                    "name": self.medicines,
                    "morning": "",
                    "afternoon": "",
                    "night": "",
                    "duration": "",
                    "instructions": self.instructions or "",
                }
            ]

        if not isinstance(rows, list):
            return []

        return [row for row in rows if isinstance(row, dict)]


def ensure_prescription_columns():
    existing_columns = {
        column["name"]
        for column in inspect(db.engine).get_columns("prescription")
    }
    prescription_columns = {
        "patient_age": "VARCHAR(20)",
        "patient_gender": "VARCHAR(30)",
        "doctor_name": "VARCHAR(100)",
        "doctor_qualification": "VARCHAR(120)",
        "doctor_specialization": "VARCHAR(120)",
        "doctor_registration_number": "VARCHAR(80)",
        "patient_history_summary": "TEXT",
        "bp": "VARCHAR(30)",
        "weight": "VARCHAR(30)",
        "pulse": "VARCHAR(30)",
        "spo2": "VARCHAR(30)",
        "lifestyle_advice": "TEXT",
        "precautions": "TEXT",
        "follow_up_notes": "TEXT",
        "follow_up_recommendation": "TEXT",
        "access_token": "VARCHAR(128)",
        "qr_filename": "VARCHAR(255)",
    }

    with db.engine.begin() as connection:
        for column_name, column_type in prescription_columns.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE prescription ADD COLUMN {column_name} {column_type}"
                )

    # Ensure every existing prescription has a secure access token.
    from app.models.prescription import Prescription as PrescriptionModel

    prescriptions_missing_token = (
        db.session.query(PrescriptionModel)
        .filter(PrescriptionModel.access_token.is_(None))
        .all()
    )
    for prescription in prescriptions_missing_token:
        prescription.access_token = secrets.token_urlsafe(32)
    if prescriptions_missing_token:
        db.session.commit()
