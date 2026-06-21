from datetime import datetime
from sqlalchemy import inspect

from app.extensions import db


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_date = db.Column(db.Date, nullable=False)
    slot_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="available")
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Slot {self.slot_date} {self.slot_time} - {self.status}>"


def ensure_slot_columns():
    existing_columns = {c['name'] for c in inspect(db.engine).get_columns('slot')} if 'slot' in inspect(db.engine).get_table_names() else set()
    required = {
        'doctor_id': 'INTEGER',
    }

    with db.engine.begin() as connection:
        for col, coltype in required.items():
            if col not in existing_columns:
                try:
                    connection.exec_driver_sql(f"ALTER TABLE slot ADD COLUMN {col} {coltype}")
                except Exception:
                    # best-effort; ignore if unable to add (existing deployments may vary)
                    pass
