from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.schemas import ReportSummary


def money(value: Decimal) -> str:
    return f"IDR {value:,.0f}"


def monthly_report_pdf(summary: ReportSummary) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 56

    title_date = date(summary.start_date.year, summary.start_date.month, 1)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(48, y, f"Monthly Spending Report - {title_date:%B %Y}")
    y -= 36

    pdf.setFont("Helvetica", 11)
    pdf.drawString(48, y, f"Period: {summary.start_date.isoformat()} to {summary.end_date.isoformat()}")
    y -= 24
    pdf.drawString(48, y, f"Income: {money(summary.income_idr)}")
    y -= 18
    pdf.drawString(48, y, f"Expenses: {money(summary.expense_idr)}")
    y -= 18
    pdf.drawString(48, y, f"Net: {money(summary.net_idr)}")
    y -= 30

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(48, y, "Category Totals")
    y -= 22

    pdf.setFont("Helvetica", 10)
    for item in summary.category_totals:
        if y < 80:
            pdf.showPage()
            y = height - 56
            pdf.setFont("Helvetica", 10)
        pdf.drawString(56, y, f"{item.category} ({item.type})")
        pdf.drawRightString(width - 56, y, money(item.total_idr))
        y -= 16

    if summary.insights:
        y -= 14
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(48, y, "Insights")
        y -= 22
        pdf.setFont("Helvetica", 10)
        for insight in summary.insights:
            if y < 80:
                pdf.showPage()
                y = height - 56
                pdf.setFont("Helvetica", 10)
            pdf.drawString(56, y, f"- {insight}")
            y -= 16

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
