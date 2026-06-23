from datetime import datetime

from sqlalchemy import inspect

from app.extensions import db


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    reason_for_visit = db.Column(db.Text, nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    preferred_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    token_number = db.Column(db.String(10), nullable=True)
    queue_number = db.Column(db.Integer, nullable=True)
    token_date = db.Column(db.Date, nullable=True)
    tracking_id = db.Column(db.String(16), nullable=True, unique=True)
    consultation_started_at = db.Column(db.DateTime, nullable=True)
    consultation_notes = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    appointment_source = db.Column(db.String(20), nullable=False, default="manual")
    invoice_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    doctor = db.relationship("User", backref="appointments")
    prescription = db.relationship(
        "Prescription",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Appointment {self.patient_name} - {self.status}>"


def ensure_queue_columns():
    existing_columns = {
        column["name"]
        for column in inspect(db.engine).get_columns("appointment")
    }
    queue_columns = {
        "token_number": "VARCHAR(10)",
        "token_date": "DATE",
        "consultation_started_at": "DATETIME",
        "consultation_notes": "TEXT",
        "completed_at": "DATETIME",
        "tracking_id": "VARCHAR(16)",
        "queue_number": "INTEGER",
        "doctor_id": "INTEGER",
        "appointment_source": "VARCHAR(20)",
        "invoice_path": "VARCHAR(500)",
    }

    with db.engine.begin() as connection:
        for column_name, column_type in queue_columns.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE appointment ADD COLUMN {column_name} {column_type}"
                )
