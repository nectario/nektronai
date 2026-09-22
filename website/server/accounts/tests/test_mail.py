"""Branding regression tests. SES is mocked; no messages are sent."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mail import Mailer


class MailBrandingTests(unittest.TestCase):
    def test_verification_and_reset_use_brand_but_preserve_legal_entity(self):
        for purpose, subject, page in (
            ("verify", "Verify your NektronAI email", "verify-email.html"),
            ("reset", "Reset your NektronAI password", "reset-password.html"),
        ):
            with self.subTest(purpose=purpose), patch("mail.boto3.client") as client:
                mailer = Mailer({"NEKTRON_AUTH_EMAIL_FROM": "Nektron <info@nektron.ai>"})
                mailer.send("recipient@example.com", purpose, "a" * 43)
                message = client.return_value.send_email.call_args.kwargs
                self.assertEqual(message["FromEmailAddress"], "NektronAI <info@nektron.ai>")
                self.assertEqual(message["Content"]["Simple"]["Subject"]["Data"], subject)
                for body in message["Content"]["Simple"]["Body"].values():
                    self.assertIn("NektronAI account", body["Data"])
                    self.assertIn("Nektron, Inc.", body["Data"])
                    self.assertIn("https://nektron.ai/" + page + "#token=", body["Data"])
                    self.assertNotRegex(body["Data"], r"\bNektron\b(?!, Inc\.)")

    def test_sender_mailbox_is_preserved(self):
        for configured, address in ((None,"info@nektron.ai"),
                                    ("accounts@example.com","accounts@example.com"),
                                    ("Old name <accounts@example.com>","accounts@example.com")):
            with self.subTest(configured=configured), patch("mail.boto3.client"):
                settings={} if configured is None else {"NEKTRON_AUTH_EMAIL_FROM":configured}
                self.assertEqual(Mailer(settings).sender, "NektronAI <" + address + ">")

    def test_account_pages_use_brand_and_keep_corporate_footer(self):
        root=Path(__file__).resolve().parents[3]
        for name in ("signup.html","login.html","account.html","verify-email.html","forgot-password.html","reset-password.html"):
            text=(root/name).read_text(encoding="utf-8")
            self.assertIn("Your NektronAI account",text)
            self.assertIn("Nektron, Inc.",text)
            self.assertNotRegex(text,r"\bNektron (account|member|products)\b")


if __name__ == "__main__":
    unittest.main()
