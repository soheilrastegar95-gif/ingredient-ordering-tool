"""
scheduled_report.py — standalone script that emails the end-of-day report
automatically. Run by a scheduled GitHub Action (see
.github/workflows/daily_report.yml) so it fires every day without anyone
needing to open the app.

Reads all config from environment variables (set as GitHub Actions secrets):
  DATABASE_URL, RESEND_API_KEY, REPORT_EMAIL_TO
"""
import os
import db
import daily_report


def main():
    to_addr = os.environ["REPORT_EMAIL_TO"]
    resend_api_key = os.environ["RESEND_API_KEY"]

    locations = db.list_locations()
    if not locations:
        print("No locations found — nothing to report.")
        return

    for loc in locations:
        subject, text_body, html_body = daily_report.build_report(loc["id"], loc["name"])
        daily_report.send_email(subject, text_body, html_body, to_addr, resend_api_key)
        print(f"Sent report for location: {loc['name']}")


if __name__ == "__main__":
    main()
