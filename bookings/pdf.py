import base64
import io

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _fmt_date(d):
    return d.strftime("%d %B %Y") if d else "—"


def _fmt_time(t):
    return t.strftime("%I:%M %p") if t else "—"


def build_booking_receipt_pdf(booking) -> io.BytesIO:
    """Renders a clean Seva Booking receipt PDF from TRUSTED backend data
    only (the `booking` instance, straight from the DB — never from
    frontend-supplied fields). Embeds the SAME encrypted Booking QR already
    used elsewhere in the system (Sec.13) — no second QR system.
    """
    seva = booking.seva
    devotee = booking.devotee

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    temple_name = getattr(settings, "TEMPLE_NAME", "Sansthan")

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, temple_name)
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#B45309"))
    c.drawCentredString(width / 2, y, "SEVA BOOKING RECEIPT")
    c.setFillColor(colors.black)
    y -= 6 * mm
    c.setLineWidth(0.5)
    c.line(margin, y, width - margin, y)
    y -= 10 * mm

    def row(label, value):
        nonlocal y
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(margin + 55 * mm, y, str(value) if value not in (None, "") else "—")
        y -= 7 * mm

    row("Booking Reference:", booking.booking_code)
    row("Devotee Name:", devotee.full_name)
    row("Devotee ID:", getattr(devotee, "devotee_code", devotee.id))
    row("Seva Name:", seva.name)
    if seva.description:
        row("Seva Description:", seva.description[:80])
    row("Start Date:", _fmt_date(seva.start_date))
    row("Start Time:", _fmt_time(seva.start_time))
    row("End Date:", _fmt_date(seva.end_date))
    row("End Time:", _fmt_time(seva.end_time))
    row("Booking Date/Time:", booking.created_at.strftime("%d %B %Y, %I:%M %p"))
    row("Booking Status:", booking.status.upper())
    row("Amount:", f"Rs. {booking.amount}")
    if booking.payment_id:
        row("Payment Reference:", booking.payment_id)

    y -= 5 * mm
    c.line(margin, y, width - margin, y)

    # --- Embed the SAME encrypted Booking QR already generated on the
    # booking model (Sec.13). Only rendered if it already exists — this
    # endpoint never mints a new/second QR system. ---
    if booking.encrypted_qr:
        from crowd_status.qr_generator import render_qr_image

        data_uri = render_qr_image(booking.encrypted_qr)
        png_bytes = base64.b64decode(data_uri.split(",", 1)[1])
        qr_img = ImageReader(io.BytesIO(png_bytes))
        qr_size = 35 * mm
        c.drawImage(
            qr_img, width - margin - qr_size, y - qr_size - 5 * mm,
            width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto",
        )
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(margin, y - qr_size / 2, "Scan this QR at the counter/entry for verification.")

    c.setFont("Helvetica", 7)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, margin / 2, "This is a system-generated receipt and does not require a signature.")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf