from datetime import datetime, time, timedelta

from app.extensions import db


class DoctorAvailability(db.Model):
    """Represents a doctor's availability window for booking appointments."""

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    availability_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    consultation_duration_minutes = db.Column(db.Integer, nullable=False, default=15)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    doctor = db.relationship("User", backref="availabilities")
    generated_slots = db.relationship(
        "GeneratedSlot",
        backref="availability",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def __repr__(self):
        return f"<DoctorAvailability {self.doctor_id} {self.availability_date} {self.start_time}-{self.end_time}>"

    def generate_slots(self):
        """Generate appointment slots for this availability window."""
        # Delete existing slots for this availability
        GeneratedSlot.query.filter_by(availability_id=self.id).delete()

        slots = []
        current_time = datetime.combine(self.availability_date, self.start_time)
        end_datetime = datetime.combine(self.availability_date, self.end_time)
        duration_delta = timedelta(minutes=self.consultation_duration_minutes)

        while current_time + duration_delta <= end_datetime:
            slot = GeneratedSlot(
                availability_id=self.id,
                slot_date=self.availability_date,
                slot_time=current_time.time(),
                status="available",
            )
            slots.append(slot)
            current_time += duration_delta

        return slots

    def overlaps_with(self, start_time, end_time):
        """Check if this availability overlaps with another time range."""
        # Convert time objects to minutes for easier comparison
        self_start = self.start_time.hour * 60 + self.start_time.minute
        self_end = self.end_time.hour * 60 + self.end_time.minute
        new_start = start_time.hour * 60 + start_time.minute
        new_end = end_time.hour * 60 + end_time.minute

        # Check for overlap
        return not (self_end <= new_start or self_start >= new_end)


class GeneratedSlot(db.Model):
    """Represents an automatically generated appointment slot from an availability window."""

    id = db.Column(db.Integer, primary_key=True)
    availability_id = db.Column(db.Integer, db.ForeignKey("doctor_availability.id"), nullable=False)
    slot_date = db.Column(db.Date, nullable=False)
    slot_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="available")
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    appointment = db.relationship("Appointment", backref="generated_slot", uselist=False)

    def __repr__(self):
        return f"<GeneratedSlot {self.slot_date} {self.slot_time} - {self.status}>"
