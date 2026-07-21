"""
daily_report.py — builds and sends the end-of-day email report.
Shared by the Streamlit app (manual "send now" button) and the
scheduled script (automatic daily send via GitHub Actions).

Uses Resend (resend.com) to send email — sends from a generic system
address (onboarding@resend.dev) rather than a personal email account.
Free tier: send to the email address you signed up to Resend with,
no domain verification needed.
"""
import requests
from datetime import date as date_type
import db

RESEND_API_URL = "https://api.resend.com/emails"


def build_report(location_id: int, location_name: str, report_date: str = None) -> tuple[str, str, str]:
    """Returns (subject, plain_text_body, html_body) for the given location and date (defaults to today)."""
    if report_date is None:
        report_date = date_type.today().isoformat()

    sales = db.get_dish_sales_for_date(location_id, report_date)
    usage = db.calculate_usage_for_date(location_id, report_date)
    order_report = db.get_order_report(location_id)
    needs_order = [r for r in order_report if r['status'] == "ORDER NOW"]

    subject = f"Daily Report — {location_name} — {report_date}"

    lines = [f"Daily Report for {location_name} — {report_date}", ""]
    lines.append("SALES TODAY:")
    if sales:
        for dish, qty in sorted(sales.items()):
            lines.append(f"  {dish}: {qty}")
    else:
        lines.append("  No sales recorded today.")
    lines.append("")
    lines.append("INGREDIENTS USED TODAY:")
    if usage:
        for ing, qty in sorted(usage.items()):
            lines.append(f"  {ing}: {qty:.2f}")
    else:
        lines.append("  No usage recorded today.")
    lines.append("")
    lines.append("NEEDS ORDERING NOW:")
    if needs_order:
        for r in needs_order:
            lines.append(f"  {r['ingredient']}: order {r['suggested_order_qty']} {r['unit']} (supplier: {r['supplier'] or 'none set'})")
    else:
        lines.append("  Everything is stocked!")
    text_body = "\n".join(lines)

    def _rows(items):
        return "".join(
            f"<tr><td style='padding:4px 10px; border-bottom:1px solid #eee;'>{a}</td>"
            f"<td style='padding:4px 10px; border-bottom:1px solid #eee;'>{b}</td></tr>"
            for a, b in items
        )

    sales_rows = _rows(sorted(sales.items())) if sales else "<tr><td colspan=2>No sales recorded today.</td></tr>"
    usage_rows = _rows([(i, f"{q:.2f}") for i, q in sorted(usage.items())]) if usage else "<tr><td colspan=2>No usage recorded today.</td></tr>"
    order_rows = _rows([
        (r['ingredient'], f"order {r['suggested_order_qty']} {r['unit']} ({r['supplier'] or 'no supplier'})")
        for r in needs_order
    ]) if needs_order else "<tr><td colspan=2>Everything is stocked!</td></tr>"

    html_body = f"""
    <html><body style="font-family: sans-serif; color: #2B2B28;">
    <h2>🍽️ Daily Report — {location_name}</h2>
    <p>{report_date}</p>
    <h3>Sales Today</h3>
    <table style="border-collapse: collapse;">{sales_rows}</table>
    <h3>Ingredients Used Today</h3>
    <table style="border-collapse: collapse;">{usage_rows}</table>
    <h3 style="color:#C1440E;">Needs Ordering Now</h3>
    <table style="border-collapse: collapse;">{order_rows}</table>
    </body></html>
    """
    return subject, text_body, html_body


def send_email(subject: str, text_body: str, html_body: str, to_addr: str, resend_api_key: str):
    response = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {resend_api_key}"},
        json={
            "from": "Ingredient Ordering Tool <onboarding@resend.dev>",
            "to": [to_addr],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend API error ({response.status_code}): {response.text}")
