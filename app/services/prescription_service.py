import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import qrcode
from flask import current_app, url_for
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
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

CLINIC_NAME = "ClinIQ Clinic"
CLINIC_ADDRESS = "Smart Health Center, Main Road, Pune, Maharashtra"
CLINIC_PHONE = "+91 98765 43210"
CLINIC_EMAIL = "care@cliniq.health"
CLINIC_WEBSITE = "www.cliniq.health"
DEFAULT_SPECIALIZATION = "Consultant Psychiatrist"
DEFAULT_QUALIFICATION = "MD"
DEFAULT_REGISTRATION_NUMBER = "REG-CLINIQ-2026"


def parse_prescription_form(form):
    errors = []
    diagnosis = form.get("diagnosis", "").strip()
    patient_age = form.get("patient_age", "").strip()
    patient_gender = form.get("patient_gender", "").strip()
    doctor_qualification = form.get("doctor_qualification", "").strip()
    doctor_specialization = form.get("doctor_specialization", "").strip()
    doctor_registration_number = form.get("doctor_registration_number", "").strip()
    patient_history_summary = form.get("patient_history_summary", "").strip()
    bp = form.get("bp", "").strip()
    weight = form.get("weight", "").strip()
    pulse = form.get("pulse", "").strip()
    spo2 = form.get("spo2", "").strip()
    lifestyle_advice = form.get("lifestyle_advice", "").strip()
    precautions = form.get("precautions", "").strip()
    follow_up_notes = form.get("follow_up_notes", "").strip()
    follow_up_recommendation = form.get("follow_up_recommendation", "").strip()
    next_visit_raw = form.get("next_visit_date", "").strip()
    medicines = _parse_medicine_rows(form)

    if not diagnosis:
        errors.append("Diagnosis is required.")

    if not medicines:
        errors.append("Add at least one medicine.")

    next_visit_date = None
    if next_visit_raw:
        try:
            next_visit_date = datetime.strptime(next_visit_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid next visit date.")

    return errors, {
        "patient_age": patient_age,
        "patient_gender": patient_gender,
        "doctor_qualification": doctor_qualification,
        "doctor_specialization": doctor_specialization,
        "doctor_registration_number": doctor_registration_number,
        "patient_history_summary": patient_history_summary,
        "bp": bp,
        "weight": weight,
        "pulse": pulse,
        "spo2": spo2,
        "diagnosis": diagnosis,
        "medicines": medicines,
        "lifestyle_advice": lifestyle_advice,
        "precautions": precautions,
        "follow_up_notes": follow_up_notes,
        "follow_up_recommendation": follow_up_recommendation,
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
    prescription.patient_age = data["patient_age"]
    prescription.patient_gender = data["patient_gender"]
    prescription.doctor_name = doctor_name
    prescription.doctor_qualification = data["doctor_qualification"] or DEFAULT_QUALIFICATION
    prescription.doctor_specialization = data["doctor_specialization"] or DEFAULT_SPECIALIZATION
    prescription.doctor_registration_number = data["doctor_registration_number"] or DEFAULT_REGISTRATION_NUMBER
    prescription.patient_history_summary = data["patient_history_summary"]
    prescription.bp = data["bp"]
    prescription.weight = data["weight"]
    prescription.pulse = data["pulse"]
    prescription.spo2 = data["spo2"]
    prescription.diagnosis = data["diagnosis"]
    prescription.medicines = json.dumps(data["medicines"])
    prescription.instructions = _medicine_summary(data["medicines"])
    prescription.lifestyle_advice = data["lifestyle_advice"]
    prescription.precautions = data["precautions"]
    prescription.follow_up_notes = data["follow_up_notes"]
    prescription.follow_up_recommendation = data["follow_up_recommendation"]
    prescription.next_visit_date = data["next_visit_date"]

    if not prescription.access_token:
        prescription.access_token = secrets.token_urlsafe(32)

    db.session.commit()

    pdf_filename = generate_prescription_pdf(prescription)
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


def get_medicine_rows(prescription):
    return _load_medicine_rows(prescription.medicines if prescription else "")


def generate_prescription_pdf(prescription):
    filename = _build_filename("prescription", prescription.id, "pdf")
    file_path = _safe_instance_file(PRESCRIPTION_DIR, filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    document = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        rightMargin=0.48 * inch,
        leftMargin=0.48 * inch,
        topMargin=0.46 * inch,
        bottomMargin=0.5 * inch,
    )

    story = []
    styles = _pdf_styles()
    story.extend(_clinic_header(styles))
    story.append(Spacer(1, 0.13 * inch))
    story.append(_doctor_card(prescription, styles))
    story.append(Spacer(1, 0.12 * inch))
    story.append(_patient_card(prescription, styles))
    story.append(Spacer(1, 0.12 * inch))
    if prescription.patient_history_summary or prescription.bp or prescription.weight or prescription.pulse or prescription.spo2:
        story.append(_history_and_vitals_card(prescription, styles))
        story.append(Spacer(1, 0.14 * inch))
    story.append(_section_card("Diagnosis", prescription.diagnosis, styles, highlighted=True))
    story.append(Spacer(1, 0.14 * inch))
    story.append(_medicine_table(get_medicine_rows(prescription), styles))
    story.append(Spacer(1, 0.14 * inch))
    story.append(_notes_table(prescription, styles))
    story.append(Spacer(1, 0.14 * inch))
    story.append(_follow_up_card(prescription, styles))
    story.append(Spacer(1, 0.22 * inch))
    story.append(_footer_signature(prescription, styles))

    document.build(
        story,
        onFirstPage=_draw_page_background,
        onLaterPages=_draw_page_background,
    )
    return filename


def generate_prescription_qr(prescription):
    filename = _build_filename("prescription-qr", prescription.id, "png")
    file_path = _safe_instance_file(QR_DIR, filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    prescription_url = url_for(
        "patient.download_prescription",
        token=prescription.access_token,
        _external=True,
    )
    image = qrcode.make(prescription_url)
    image.save(file_path)
    return filename


def _clinic_header(styles):
    logo = Paragraph("+", styles["Logo"])
    clinic = [
        Paragraph(CLINIC_NAME, styles["ClinicName"]),
        Paragraph(
            f"{CLINIC_ADDRESS}<br/>{CLINIC_PHONE} | {CLINIC_EMAIL} | {CLINIC_WEBSITE}",
            styles["SmallMuted"],
        ),
    ]
    header = Table(
        [[logo, clinic, Paragraph("DIGITAL PRESCRIPTION", styles["PrescriptionLabel"])]],
        colWidths=[0.55 * inch, 4.1 * inch, 2.15 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7fbfa")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#d8e7e4")),
                ("LINEBELOW", (0, 0), (-1, -1), 2, colors.HexColor("#0f766e")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return [header]


def _doctor_card(prescription, styles):
    appointment = prescription.appointment
    data = [
        [
            _label_value("Doctor", prescription.doctor_name or "ClinIQ Doctor", styles),
            _label_value("Qualification", prescription.doctor_qualification or DEFAULT_QUALIFICATION, styles),
        ],
        [
            _label_value("Specialization", prescription.doctor_specialization or DEFAULT_SPECIALIZATION, styles),
            _label_value("Registration No.", prescription.doctor_registration_number or DEFAULT_REGISTRATION_NUMBER, styles),
        ],
        [
            _label_value("Consultation Date", prescription.created_at.strftime("%d %b %Y"), styles),
            _label_value("Consultation ID", f"CLQ-{appointment.id:05d}", styles),
        ],
    ]
    return _card_table(data, [3.35 * inch, 3.35 * inch], "#edf6f4")


def _patient_card(prescription, styles):
    appointment = prescription.appointment
    data = [
        [
            _label_value("Patient Name", prescription.patient_name, styles),
            _label_value("Phone Number", appointment.phone_number, styles),
        ],
        [
            _label_value("Age", prescription.patient_age or "Not specified", styles),
            _label_value("Gender", prescription.patient_gender or "Not specified", styles),
        ],
        [
            _label_value("Appointment Token", appointment.token_number or "Not assigned", styles),
            _label_value("Visit Reason", appointment.reason_for_visit, styles),
        ],
    ]
    return _card_table(data, [3.35 * inch, 3.35 * inch], "#ffffff")


def _history_and_vitals_card(prescription, styles):
    rows = []
    if prescription.patient_history_summary:
        rows.append(
            [
                Paragraph("History Summary", styles["SectionTitle"]),
                Paragraph(_linebreaks(prescription.patient_history_summary), styles["Body"]),
                "",
                "",
            ]
        )

    rows.append(
        [
            _label_value("BP", prescription.bp or "—", styles),
            _label_value("Weight", prescription.weight or "—", styles),
            _label_value("Pulse", prescription.pulse or "—", styles),
            _label_value("SpO2", prescription.spo2 or "—", styles),
        ]
    )

    column_widths = [1.85 * inch, 1.85 * inch, 1.85 * inch, 1.85 * inch]
    table = Table(rows, colWidths=column_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef7f4")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#b9ceca")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e7e4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("SPAN", (0, 0), (-1, 0)),
            ]
        )
    )
    return table


def _section_card(title, text, styles, highlighted=False):
    background = "#e7f8ef" if highlighted else "#ffffff"
    table = Table(
        [[Paragraph(title, styles["SectionTitle"])], [Paragraph(_linebreaks(text or "Not specified"), styles["Body"])]],
        colWidths=[6.7 * inch],
    )
    table.setStyle(_card_style(background))
    return table


def _medicine_table(rows, styles):
    header = ["Medicine Name", "Morning", "Afternoon", "Night", "Duration", "Instructions"]
    table_data = [[Paragraph(cell, styles["TableHeader"]) for cell in header]]

    for row in rows:
        table_data.append(
            [
                Paragraph(_clean(row.get("name", "")), styles["TableBody"]),
                Paragraph(_clean(row.get("morning", "")) or "-", styles["TableBodyCenter"]),
                Paragraph(_clean(row.get("afternoon", "")) or "-", styles["TableBodyCenter"]),
                Paragraph(_clean(row.get("night", "")) or "-", styles["TableBodyCenter"]),
                Paragraph(_clean(row.get("duration", "")) or "-", styles["TableBody"]),
                Paragraph(_clean(row.get("instructions", "")) or "-", styles["TableBody"]),
            ]
        )

    table = Table(
        table_data,
        colWidths=[1.58 * inch, 0.72 * inch, 0.82 * inch, 0.62 * inch, 0.92 * inch, 2.04 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b5f59")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#b9ceca")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e7e4")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ffffff")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _notes_table(prescription, styles):
    data = [
        [Paragraph("Lifestyle Advice", styles["SectionTitle"]), Paragraph(_linebreaks(prescription.lifestyle_advice or "Not specified"), styles["Body"])],
        [Paragraph("Precautions", styles["SectionTitle"]), Paragraph(_linebreaks(prescription.precautions or "Not specified"), styles["Body"])],
        [Paragraph("Follow-up Notes", styles["SectionTitle"]), Paragraph(_linebreaks(prescription.follow_up_notes or "Not specified"), styles["Body"])],
    ]
    table = Table(data, colWidths=[1.65 * inch, 5.05 * inch])
    table.setStyle(_card_style("#ffffff"))
    return table


def _follow_up_card(prescription, styles):
    next_visit = (
        prescription.next_visit_date.strftime("%d %b %Y")
        if prescription.next_visit_date
        else "Not specified"
    )
    data = [
        [
            _label_value("Next Visit Date", next_visit, styles),
            _label_value(
                "Follow-up Recommendation",
                prescription.follow_up_recommendation or "Follow as advised by doctor.",
                styles,
            ),
        ]
    ]
    return _card_table(data, [2.1 * inch, 4.6 * inch], "#fff7d6")


def _footer_signature(prescription, styles):
    signature = Table(
        [
            [
                Paragraph("Digital Signature", styles["SmallMuted"]),
                Paragraph("Generated by ClinIQ", styles["GeneratedBy"]),
            ],
            [
                HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#8aa09b")),
                "",
            ],
            [
                Paragraph(prescription.doctor_name or "ClinIQ Doctor", styles["SignatureName"]),
                Paragraph("This is a digitally generated prescription.", styles["SmallMutedRight"]),
            ],
        ],
        colWidths=[2.5 * inch, 4.2 * inch],
    )
    signature.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return signature


def _draw_page_background(canvas, document):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0f766e"))
    try:
        canvas.setFillAlpha(0.055)
    except AttributeError:
        pass
    canvas.setFont("Helvetica-Bold", 86)
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, "ClinIQ")
    canvas.restoreState()

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d8e7e4"))
    canvas.setLineWidth(0.7)
    canvas.line(0.48 * inch, 0.38 * inch, A4[0] - 0.48 * inch, 0.38 * inch)
    canvas.restoreState()


def _pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Logo", fontName="Helvetica-Bold", fontSize=24, leading=26, textColor=colors.white, alignment=TA_CENTER, backColor=colors.HexColor("#0f766e"), borderPadding=6))
    styles.add(ParagraphStyle("ClinicName", fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=colors.HexColor("#0b5f59")))
    styles.add(ParagraphStyle("PrescriptionLabel", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.HexColor("#0b5f59"), alignment=TA_RIGHT))
    styles.add(ParagraphStyle("SmallMuted", fontSize=8.3, leading=11, textColor=colors.HexColor("#5c6d76")))
    styles.add(ParagraphStyle("SmallMutedRight", parent=styles["SmallMuted"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle("Label", fontName="Helvetica-Bold", fontSize=7.6, leading=9, textColor=colors.HexColor("#5c6d76")))
    styles.add(ParagraphStyle("Value", fontName="Helvetica-Bold", fontSize=9.6, leading=12, textColor=colors.HexColor("#15242d")))
    styles.add(ParagraphStyle("SectionTitle", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=colors.HexColor("#0b5f59")))
    styles.add(ParagraphStyle("Body", fontSize=9.2, leading=13, textColor=colors.HexColor("#15242d")))
    styles.add(ParagraphStyle("TableHeader", fontName="Helvetica-Bold", fontSize=8.2, leading=10, textColor=colors.white, alignment=TA_CENTER))
    styles.add(ParagraphStyle("TableBody", fontSize=8.2, leading=10.5, textColor=colors.HexColor("#15242d")))
    styles.add(ParagraphStyle("TableBodyCenter", parent=styles["TableBody"], alignment=TA_CENTER))
    styles.add(ParagraphStyle("GeneratedBy", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.HexColor("#0b5f59"), alignment=TA_RIGHT))
    styles.add(ParagraphStyle("SignatureName", fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=colors.HexColor("#15242d")))
    return styles


def _card_table(data, col_widths, background):
    table = Table(data, colWidths=col_widths)
    table.setStyle(_card_style(background))
    return table


def _card_style(background):
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#b9ceca")),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e7e4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
    )


def _label_value(label, value, styles):
    return [
        Paragraph(label, styles["Label"]),
        Paragraph(_linebreaks(value or "Not specified"), styles["Value"]),
    ]


def _parse_medicine_rows(form):
    names = _form_list(form, "medicine_name")
    mornings = _form_list(form, "medicine_morning")
    afternoons = _form_list(form, "medicine_afternoon")
    nights = _form_list(form, "medicine_night")
    durations = _form_list(form, "medicine_duration")
    instructions = _form_list(form, "medicine_instructions")
    max_length = max(
        len(names),
        len(mornings),
        len(afternoons),
        len(nights),
        len(durations),
        len(instructions),
        0,
    )

    rows = []
    for index in range(max_length):
        name = _list_value(names, index)
        row = {
            "name": name,
            "morning": _list_value(mornings, index),
            "afternoon": _list_value(afternoons, index),
            "night": _list_value(nights, index),
            "duration": _list_value(durations, index),
            "instructions": _list_value(instructions, index),
        }
        if any(row.values()) and name:
            rows.append(row)

    legacy_medicines = form.get("medicines", "").strip()
    if not rows and legacy_medicines:
        rows.append(
            {
                "name": legacy_medicines,
                "morning": "",
                "afternoon": "",
                "night": "",
                "duration": "",
                "instructions": form.get("instructions", "").strip(),
            }
        )

    return rows


def _load_medicine_rows(value):
    if not value:
        return []

    try:
        rows = json.loads(value)
    except json.JSONDecodeError:
        return [
            {
                "name": value,
                "morning": "",
                "afternoon": "",
                "night": "",
                "duration": "",
                "instructions": "",
            }
        ]

    if not isinstance(rows, list):
        return []

    return [row for row in rows if isinstance(row, dict)]


def _medicine_summary(rows):
    return "\n".join(
        (
            f"{row.get('name', '')} | M:{row.get('morning', '-') or '-'} "
            f"A:{row.get('afternoon', '-') or '-'} N:{row.get('night', '-') or '-'} | "
            f"{row.get('duration', '')} | {row.get('instructions', '')}"
        ).strip()
        for row in rows
    )


def _form_list(form, key):
    if hasattr(form, "getlist"):
        return [value.strip() for value in form.getlist(key)]

    value = form.get(key, [])
    if isinstance(value, list):
        return [item.strip() for item in value]

    return [value.strip()] if value else []


def _list_value(values, index):
    return values[index].strip() if index < len(values) else ""


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


def _clean(value):
    return escape(str(value or ""))
