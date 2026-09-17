"""Nektron account emails; tokens never appear in API responses or routine logs."""
from html import escape
from urllib.parse import quote

import boto3
from botocore.config import Config


class Mailer:
    def __init__(self, settings):
        self.origin = settings.get("NEKTRON_SITE_ORIGIN", "https://nektron.ai").rstrip("/")
        self.sender = settings.get("NEKTRON_AUTH_EMAIL_FROM", "Nektron <info@nektron.ai>")
        self.client = boto3.client("sesv2", region_name=settings.get("NEKTRON_EMAIL_REGION", "us-east-2"),
                                   config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}))

    def send(self, email, purpose, token):
        verify = purpose == "verify"
        title = "Verify your Nektron email" if verify else "Reset your Nektron password"
        action = "Verify email" if verify else "Choose a new password"
        detail = ("Confirm your email address to finish creating your Nektron account."
                  if verify else "We received a request to set a new password for your Nektron account.")
        lifetime = "24 hours" if verify else "30 minutes"
        page = "verify-email.html" if verify else "reset-password.html"
        # A fragment keeps the bearer token out of webserver request logs/referrers.
        url = self.origin + "/" + page + "#token=" + quote(token, safe="")
        text = f"{title}\n\n{detail}\n\n{action}: {url}\n\nThis link expires in {lifetime} and works once. If you did not request it, ignore this email.\n\nNektron, Inc.\ninfo@nektron.ai"
        html = f"""<!doctype html><html><body style="margin:0;background:#f8fafc;color:#142a40;font-family:Arial,sans-serif">
        <div style="max-width:560px;margin:40px auto;padding:32px;background:white;border:1px solid #d1deea;border-radius:16px">
        <p style="color:#17617c;font-weight:bold">NektronAI</p><h1 style="font-size:26px">{title}</h1>
        <p style="line-height:1.7">{detail}</p>
        <p style="margin:28px 0"><a href="{escape(url, quote=True)}" style="display:inline-block;background:#17617c;color:white;text-decoration:none;padding:14px 22px;border-radius:10px">{action}</a></p>
        <p style="line-height:1.7;font-size:14px;color:#435d73">This link expires in {lifetime} and works once. If you did not request it, ignore this email.</p>
        <p style="font-size:13px;color:#435d73">Nektron, Inc. &middot; info@nektron.ai</p></div></body></html>"""
        self.client.send_email(FromEmailAddress=self.sender, Destination={"ToAddresses": [email]},
            Content={"Simple": {"Subject": {"Data": title, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": text, "Charset": "UTF-8"},
                         "Html": {"Data": html, "Charset": "UTF-8"}}}})
