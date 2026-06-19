import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

import qrcode
from flask import current_app, url_for
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.extensions import db
from app.models.appointment import Appointment
from app.models.prescription import Prescription


PRESCRIPTION_DIR = "prescriptions"
QR_DIR = "prescription_qr"


def parse_prescription_form(form):
    errors = []
    diagnosis = form.get("diagnosis", "").strip()
    medicines = form.get("medicines", "").strip()
    instructions = form.get("instructions", "").strip()
    next_visit_raw = form.get("next_visit_date", "").strip()

    if not diagnosis:
        errors.append("Diagnosis is required.")

    if not medicines:
        errors.append("Medicines are required.")

    next_visit_date = None
    if next_visit_raw:
        try:
            next_visit_date = datetime.strptime(next_visit_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid next visit date.")

    return errors, {
        "diagnosis": diagnosis,
        "medicines": medicines,
        "instructions": instructions,
        "next_visit_date": next_visit_date,
    }


def create_or_update_prescription(appointment_id, form, doctor_name):
    appointment = db.get_or_404(Appointment, appointment_id)

    if appointment.status not in {"in_consultation", "completed"}:
        raise ValueError("Prescription can only be created during or after consultation.")

    errors, data = parse_prescription_form(form)
    if errors:
        return errors, None

    prescription = appointment.prescription
    if prescription is None:
        prescription = Prescription(
            appointment=appointment,
            patient_name=appointment.patient_name,
        )
        db.session.add(prescription)

    prescription.patient_name = appointment.patient_name
    prescription.diagnosis = data["diagnosis"]
    prescription.medicines = data["medicines"]
    prescription.instructions = data["instructions"]
    prescription.next_visit_date = data["next_visit_date"]
    db.session.commit()

    pdf_filename = generate_prescription_pdf(prescription, doctor_name)
    qr_filename = generate_prescription_qr(prescription)
    prescription.pdf_filename = pdf_filename
    prescription.qr_filename = qr_filename
    db.session.commit()

    return [], prescription


def get_prescription_file_path(prescription):
    if not prescription or not prescription.pdf_filename:
        return None

    return _safe_instance_file(PRESCRIPTION_DIR, prescription.pdf_filename)


def get_qr_file_path(prescription):
    if not prescription or not prescription.qr_filename:
        return None

    return _safe_instance_file(QR_DIR, prescription.qr_filename)


def generate_prescription_pdf(prescription, doctor_name):
    filename = _build_filename("prescription", prescription.id, "pdf")
    file_path = _safe_instance_file(PRESCRIPTION_DIR, filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    appointment = prescription.appointment
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading3"]
    body_style = styles["BodyText"]

    document = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )

    details = [
        ["Doctor Name", doctor_name],
        ["Patient Name", prescription.patient_name],
        ["Date", prescription.created_at.strftime("%d %b %Y")],
        ["Appointment Token", appointment.token_number or "Not assigned"],
        [
            "Next Visit Date",
            prescription.next_visit_date.strftime("%d %b %Y")
            if prescription.next_visit_date
            else "Not specified",
        ],
    ]

    content = [
        Paragraph("ClinIQ Clinic", title_style),
        Paragraph("Digital Prescription", styles["Heading2"]),
        Spacer(1, 0.18 * inch),
        Table(details, colWidths=[1.65 * inch, 4.6 * inch]),
        Spacer(1, 0.28 * inch),
        Paragraph("Diagnosis", heading_style),
        Paragraph(_linebreaks(prescription.diagnosis), body_style),
        Spacer(1, 0.18 * inch),
        Paragraph("Medicines", heading_style),
        Paragraph(_linebreaks(prescription.medicines), body_style),
        Spacer(1, 0.18 * inch),
        Paragraph("Instructions", heading_style),
        Paragraph(_linebreaks(prescription.instructions or "Not specified"), body_style),
    ]

    content[3].setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dff3f0")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0b5f59")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8e7e4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    document.build(content)
    return filename


def generate_prescription_qr(prescription):
    filename = _build_filename("prescription-qr", prescription.id, "png")
    file_path = _safe_instance_file(QR_DIR, filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    prescription_url = url_for(
        "patient.download_prescription",
        prescription_id=prescription.id,
        _external=True,
    )
    image = qrcode.make(prescription_url)
    image.save(file_path)
    return filename


def _safe_instance_file(directory, filename):
    base_directory = Path(current_app.instance_path, directory).resolve()
    file_path = (base_directory / os.path.basename(filename)).resolve()

    if base_directory not in file_path.parents and file_path != base_directory:
        raise ValueError("Unsafe file path.")

    return file_path


def _build_filename(prefix, prescription_id, extension):
    return f"{prefix}-{prescription_id}-{uuid4().hex}.{extension}"


def _linebreaks(value):
    return "<br/>".join(escape(line) for line in (value or "").splitlines())
