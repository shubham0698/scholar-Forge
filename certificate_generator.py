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


def draw_dummy_signature_alexander(c, x, y):
    """Draws an authentic handwritten ink signature for Dr. Alexander Vance."""
    c.saveState()
    c.setStrokeColor(HexColor("#1e3a8a")) # Deep Royal Ink Blue
    c.setLineWidth(1.6)
    
    path = c.beginPath()
    # 'Dr. A' loop
    path.moveTo(x + 5, y + 8)
    path.curveTo(x + 10, y + 28, x + 22, y + 32, x + 28, y + 10)
    path.curveTo(x + 32, y + 4, x + 38, y + 18, x + 48, y + 22)
    path.moveTo(x + 16, y + 18)
    path.lineTo(x + 42, y + 16)
    
    # 'Vance' cursive flourish
    path.moveTo(x + 55, y + 24)
    path.curveTo(x + 60, y + 6, x + 68, y + 8, x + 76, y + 20)
    path.curveTo(x + 82, y + 12, x + 90, y + 15, x + 98, y + 11)
    path.curveTo(x + 104, y + 18, x + 112, y + 9, x + 128, y + 22)
    c.drawPath(path, fill=False, stroke=True)
    
    # Signature underline flourish
    c.setLineWidth(1.1)
    path2 = c.beginPath()
    path2.moveTo(x + 10, y + 4)
    path2.curveTo(x + 50, y + 1, x + 90, y + 3, x + 135, y + 6)
    c.drawPath(path2, fill=False, stroke=True)
    
    c.restoreState()

def draw_dummy_signature_generic(c, x, y):
    """Draws a stylized handwritten ink signature for co-signers."""
    c.saveState()
    c.setStrokeColor(HexColor("#0f172a")) # Dark Ink
    c.setLineWidth(1.4)
    
    path = c.beginPath()
    path.moveTo(x + 5, y + 12)
    path.curveTo(x + 15, y + 30, x + 25, y + 5, x + 35, y + 24)
    path.curveTo(x + 45, y + 10, x + 55, y + 22, x + 65, y + 8)
    path.curveTo(x + 75, y + 20, x + 85, y + 6, x + 105, y + 18)
    c.drawPath(path, fill=False, stroke=True)
    
    path2 = c.beginPath()
    path2.moveTo(x + 8, y + 4)
    path2.curveTo(x + 45, y + 1, x + 80, y + 3, x + 115, y + 5)
    c.drawPath(path2, fill=False, stroke=True)
    
    c.restoreState()

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
    cert_type='publication',
    doi=None,
    paper_url=None
):
    """
    Generate a professional landscape PDF certificate dynamically in memory.
    Expanded border by -5px margin outwards for maximum inner canvas space.
    Does NOT store PDF files on disk. Returns an in-memory io.BytesIO stream.
    """
    import io
    pdf_buffer = io.BytesIO()

    width, height = landscape(A4)
    c = canvas.Canvas(pdf_buffer, pagesize=landscape(A4))

    # --- Background ---
    c.setFillColor(HexColor("#ffffff"))
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # --- Color Palette Selection based on layout type ---
    if cert_type == 'presentation':
        primary_color = HexColor("#0284c7")  # Deep Sky Blue
        secondary_color = HexColor("#0f172a") # Dark Slate
        accent_gold = HexColor("#d97706")     # Amber Gold
        border_light = HexColor("#bae6fd")    # Light Blue Accent
        layout_title = "CERTIFICATE OF PUBLICATION & PRESENTATION"
        badge_title = "INTERNATIONAL ACADEMIC RESEARCH CONFERENCE"
    else:
        primary_color = HexColor("#4f46e5")  # Indigo Primary
        secondary_color = HexColor("#1e293b") # Deep Dark Blue
        accent_gold = HexColor("#f59e0b")     # Warm Gold
        border_light = HexColor("#c7d2fe")    # Soft Indigo Accent
        layout_title = "CERTIFICATE OF PUBLICATION"
        badge_title = "OPEN ACCESS ACADEMIC REPOSITORY"

    # --- Expanded Double Decorative Borders & Guilloche Frame (-5px margin shift outwards) ---
    # Outer Border (Shifted 5px outward to 23px)
    c.setStrokeColor(primary_color)
    c.setLineWidth(3.5)
    c.rect(23, 23, width - 46, height - 46, fill=False, stroke=True)

    # Inner Gold Border (Shifted 5px outward to 31px)
    c.setStrokeColor(accent_gold)
    c.setLineWidth(1.25)
    c.rect(31, 31, width - 62, height - 62, fill=False, stroke=True)

    # Corner Flourishes
    for (cx, cy) in [(31, 31), (31, height - 31), (width - 31, 31), (width - 31, height - 31)]:
        c.setFillColor(primary_color)
        c.circle(cx, cy, 3, fill=True, stroke=False)

    # Top & Bottom Color Accent Strips
    c.setFillColor(primary_color)
    c.rect(31, height - 37, width - 62, 6, fill=True, stroke=False)
    c.rect(31, 31, width - 62, 6, fill=True, stroke=False)

    # --- TOP LEFT LOGO PLACEMENT (With 5px Top Margin) ---
    logo_path = os.path.join('static', 'img', 'logo.png')
    logo_x = 50
    logo_y = height - 110
    logo_w = 0.95 * inch
    logo_h = 0.95 * inch

    if os.path.exists(logo_path):
        logo_img = ImageReader(logo_path)
        c.drawImage(
            logo_img,
            logo_x,
            logo_y,
            width=logo_w,
            height=logo_h,
            preserveAspectRatio=True,
            mask='auto'
        )

    # Top Left Brand Header Next to Logo
    brand_text_x = logo_x + logo_w + 12
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(brand_text_x, height - 78, "SCHOLARFORGE")

    c.setFillColor(HexColor("#64748b"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(brand_text_x, height - 91, badge_title)

    # --- TOP RIGHT HEADER BADGE ---
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(primary_color)
    c.drawRightString(width - 55, height - 75, "OFFICIAL VERIFIED CERTIFICATE")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#64748b"))
    c.drawRightString(width - 55, height - 88, f"REF ID: {certificate_id}")

    # --- CENTER CERTIFICATE TITLE ---
    c.setFillColor(secondary_color)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 145, layout_title)

    c.setStrokeColor(accent_gold)
    c.setLineWidth(2)
    c.line(width / 2 - 110, height - 158, width / 2 + 110, height - 158)

    # --- CERTIFICATE BODY TEXT ---
    c.setFillColor(HexColor("#475569"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, height - 188, "THIS IS TO CERTIFY THAT")

    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 216, author_name.upper())

    if institution:
        c.setFillColor(HexColor("#64748b"))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(width / 2, height - 234, f"from {institution}")

    c.setFillColor(HexColor("#475569"))
    c.setFont("Helvetica", 11)
    if cert_type == 'presentation':
        c.drawCentredString(width / 2, height - 258, "has presented and published the peer-reviewed research paper titled")
    else:
        c.drawCentredString(width / 2, height - 258, "has peer-reviewed, verified, and published the original research paper titled")

    c.setFillColor(secondary_color)
    c.setFont("Helvetica-Bold", 14)
    display_title = paper_title if len(paper_title) <= 65 else paper_title[:62] + "..."
    c.drawCentredString(width / 2, height - 284, f'"{display_title}"')

    c.setFillColor(HexColor("#475569"))
    c.setFont("Helvetica", 10)
    if cert_type == 'presentation':
        c.drawCentredString(width / 2, height - 308, "at the ScholarForge International Academic Research Conference & Open Repository.")
    else:
        c.drawCentredString(width / 2, height - 308, "in the ScholarForge Open Access International Academic Repository.")

    # --- METADATA BOX ROW ---
    y_meta = height - 355
    box_w = width - 110
    c.setFillColor(HexColor("#f8fafc"))
    c.setStrokeColor(border_light)
    c.setLineWidth(1)
    c.roundRect(55, y_meta - 10, box_w, 36, 4, fill=True, stroke=True)

    col1 = 70
    col2 = 240
    col3 = 410
    col4 = 590

    c.setFont("Helvetica", 7.5)
    c.setFillColor(HexColor("#64748b"))
    c.drawString(col1, y_meta + 14, "PUBLICATION ID")
    c.drawString(col2, y_meta + 14, "CATEGORY")
    c.drawString(col3, y_meta + 14, "DOI REFERENCE")
    c.drawString(col4, y_meta + 14, "DATE OF ISSUE")

    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(secondary_color)
    c.drawString(col1, y_meta, publication_id or f"SF-2026-{certificate_id[:6]}")
    c.drawString(col2, y_meta, category or "General Research")
    c.drawString(col3, y_meta, doi or f"10.5555/SF.2026.{certificate_id[-5:]}")
    c.drawString(col4, y_meta, issue_date.strftime("%B %d, %Y"))

    # --- AUTHORIZED SIGNATURES ROW (With Dummy Signature Graphics) ---
    y_sig = 82

    # Left Signature: Dr. Alexander Vance (Editor-in-Chief)
    draw_dummy_signature_alexander(c, 85, y_sig + 16)

    c.setStrokeColor(HexColor("#94a3b8"))
    c.setLineWidth(0.75)
    c.line(80, y_sig + 15, 230, y_sig + 15)

    c.setFillColor(secondary_color)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(80, y_sig, "Dr. Alexander Vance")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#64748b"))
    c.drawString(80, y_sig - 10, "Editor-in-Chief, ScholarForge")

    # Middle Signature: Program Committee Chair / Guide / Conference Chair
    draw_dummy_signature_generic(c, 285, y_sig + 16)
    c.line(280, y_sig + 15, 430, y_sig + 15)
    c.setFillColor(secondary_color)
    c.setFont("Helvetica-Bold", 9.5)
    if guide_name:
        c.drawString(280, y_sig, guide_name[:25])
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#64748b"))
        c.drawString(280, y_sig - 10, "Faculty Supervisor / Guide")
    elif cert_type == 'presentation':
        c.drawString(280, y_sig, "Prof. Marcus Thorne")
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#64748b"))
        c.drawString(280, y_sig - 10, "Conference General Chair")
    else:
        c.drawString(280, y_sig, "Prof. Elena Rostova")
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#64748b"))
        c.drawString(280, y_sig - 10, "Chair, Peer Review Board")

    # --- PAPER URL & VERIFICATION FOOTER TEXT ---
    c.setFont("Helvetica", 7.5)
    c.setFillColor(HexColor("#64748b"))
    if paper_url:
        c.drawString(55, 48, f"Paper URL: {paper_url}")
        c.drawString(55, 38, f"Verify URL: {verify_url}")
    else:
        c.drawString(55, 42, f"Verify URL: {verify_url}")

    # --- RIGHT QR CODE EMBED ---
    if qr_code_path and os.path.exists(qr_code_path):
        qr_img = ImageReader(qr_code_path)
        qr_size = 1.05 * inch
        qr_x = width - 150
        qr_y = 52
        c.drawImage(
            qr_img,
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
        )
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(HexColor("#64748b"))
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer
