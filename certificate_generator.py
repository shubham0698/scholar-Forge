"""
Certificate generator for ScholarForge.
Creates professional PDF certificates with embedded QR codes.
"""

import os
import uuid
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


CERT_DIR = os.path.join('static', 'certificates')
QR_DIR = os.path.join('static', 'qrcodes')


def ensure_dirs():
    """Create output directories if they don't exist."""
    os.makedirs(CERT_DIR, exist_ok=True)
    os.makedirs(QR_DIR, exist_ok=True)


def generate_certificate_id():
    """Generate a unique certificate ID: SF-CERT-XXXXXXXX"""
    return f"SF-CERT-{uuid.uuid4().hex[:8].upper()}"


def generate_publication_id():
    """Generate a unique publication ID: SF-YYYY-NNNN"""
    year = datetime.utcnow().year
    random_part = uuid.uuid4().hex[:4].upper()
    return f"SF-{year}-{random_part}"


def generate_qr_code(data, filename):
    """Generate a QR code image and return its path."""
    ensure_dirs()
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#4f46e5", back_color="white")
    path = os.path.join(QR_DIR, filename)
    img.save(path)
    return path


def generate_certificate_pdf(
    certificate_id,
    paper_title,
    author_name,
    publication_id,
    category,
    institution,
    guide_name,
    issue_date,
    verify_url,
    qr_code_path,
):
    """
    Generate a professional landscape PDF certificate.
    Returns the file path of the generated PDF.
    """
    ensure_dirs()
    filename = f"{certificate_id}.pdf"
    filepath = os.path.join(CERT_DIR, filename)

    width, height = landscape(A4)
    c = canvas.Canvas(filepath, pagesize=landscape(A4))

    # --- Background ---
    c.setFillColor(HexColor("#ffffff"))
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # --- Decorative border ---
    border_color = HexColor("#4f46e5")
    accent_color = HexColor("#818cf8")

    # Outer border
    c.setStrokeColor(border_color)
    c.setLineWidth(3)
    c.rect(30, 30, width - 60, height - 60, fill=False, stroke=True)

    # Inner border
    c.setStrokeColor(accent_color)
    c.setLineWidth(1)
    c.rect(40, 40, width - 80, height - 80, fill=False, stroke=True)

    # --- Top accent line ---
    c.setFillColor(border_color)
    c.rect(40, height - 48, width - 80, 8, fill=True, stroke=False)

    # --- Logo & Header ---
    logo_path = os.path.join('static', 'img', 'logo.png')
    if os.path.exists(logo_path):
        # Draw logo centered at the top
        logo_img = ImageReader(logo_path)
        logo_size = 0.8 * inch
        # Draw logo next to the title
        c.drawImage(
            logo_img,
            width / 2 - 130,
            height - 100,
            width=logo_size,
            height=logo_size,
            preserveAspectRatio=True,
            mask='auto'
        )
        
        c.setFillColor(HexColor("#4f46e5"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(width / 2 - 40, height - 75, "SCHOLARFORGE")
        
        c.setFillColor(HexColor("#94a3b8"))
        c.setFont("Helvetica", 10)
        c.drawString(width / 2 - 40, height - 90, "Academic Research Publication Platform")
    else:
        # Fallback if no logo
        c.setFillColor(HexColor("#4f46e5"))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, height - 85, "SCHOLARFORGE")

        c.setFillColor(HexColor("#94a3b8"))
        c.setFont("Helvetica", 10)
        c.drawCentredString(width / 2, height - 100, "Academic Research Publication Platform")

    # --- Title ---
    c.setFillColor(HexColor("#1e293b"))
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height - 150, "Certificate of Publication")

    # --- Decorative line ---
    c.setStrokeColor(HexColor("#f59e0b"))
    c.setLineWidth(2)
    c.line(width / 2 - 80, height - 165, width / 2 + 80, height - 165)

    # --- Body text ---
    c.setFillColor(HexColor("#475569"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 200, "This is to certify that the research paper titled")

    # Paper title (may need wrapping for long titles)
    c.setFillColor(HexColor("#1e293b"))
    c.setFont("Helvetica-Bold", 16)
    # Truncate long titles
    display_title = paper_title if len(paper_title) <= 60 else paper_title[:57] + "..."
    c.drawCentredString(width / 2, height - 230, f'"{display_title}"')

    c.setFillColor(HexColor("#475569"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 260, "authored by")

    c.setFillColor(HexColor("#4f46e5"))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 290, author_name)

    if institution:
        c.setFillColor(HexColor("#475569"))
        c.setFont("Helvetica", 11)
        c.drawCentredString(width / 2, height - 312, f"from {institution}")

    c.setFillColor(HexColor("#475569"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        width / 2, height - 340,
        "has been published on the ScholarForge platform."
    )

    # --- Details row ---
    y_details = height - 385
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawString(80, y_details + 12, "PUBLICATION ID")
    c.drawString(280, y_details + 12, "CATEGORY")
    c.drawString(480, y_details + 12, "DATE OF ISSUE")

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(HexColor("#1e293b"))
    c.drawString(80, y_details - 4, publication_id)
    c.drawString(280, y_details - 4, category)
    c.drawString(480, y_details - 4, issue_date.strftime("%B %d, %Y"))

    if guide_name:
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#94a3b8"))
        c.drawString(650, y_details + 12, "GUIDE")
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(HexColor("#1e293b"))
        c.drawString(650, y_details - 4, guide_name)

    # --- QR Code ---
    if qr_code_path and os.path.exists(qr_code_path):
        qr_img = ImageReader(qr_code_path)
        qr_size = 1.1 * inch
        c.drawImage(
            qr_img,
            width - 130,
            55,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
        )
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#94a3b8"))
        c.drawCentredString(width - 130 + qr_size / 2, 48, "Scan to verify")

    # --- Certificate ID footer ---
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawString(60, 55, f"Certificate ID: {certificate_id}")
    c.drawString(60, 43, f"Verify at: {verify_url}")

    # --- Bottom accent line ---
    c.setFillColor(border_color)
    c.rect(40, 40, width - 80, 4, fill=True, stroke=False)

    c.save()
    return filepath
