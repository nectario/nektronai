"""Account-mail abuse checks; CSRF alone is not human verification."""
import json
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


SMS_GATEWAYS = frozenset(("txt.att.net", "mms.att.net", "vtext.com", "vzwpix.com",
                          "tmomail.net", "messaging.sprintpcs.com", "pm.sprint.com"))


class MailAbuseGuard:
    def __init__(self, settings):
        self.site_key = settings.get("NEKTRON_TURNSTILE_SITE_KEY", "")
        self.secret_key = settings.get("NEKTRON_TURNSTILE_SECRET_KEY", "")
        if bool(self.site_key) != bool(self.secret_key):
            raise ValueError("Both Turnstile keys must be configured")
        self.hostname = urlparse(settings.get("NEKTRON_SITE_ORIGIN", "https://nektron.ai")).hostname
        self.blocked_domains = SMS_GATEWAYS | frozenset(
            d.strip().lower() for d in settings.get("NEKTRON_ACCOUNT_BLOCKED_EMAIL_DOMAINS", "").split(",") if d.strip())

    def blocked_recipient(self, email):
        domain = email.rsplit("@", 1)[1]
        return any(domain == blocked or domain.endswith("." + blocked) for blocked in self.blocked_domains)

    def verify(self, token, action, ip):
        if not self.site_key:
            return True
        if not isinstance(token, str) or not token or len(token) > 2048:
            return False
        # Tokens are single-use. Never trust a browser's reported challenge result.
        body = urlencode({"secret": self.secret_key, "response": token, "remoteip": ip}).encode()
        request = Request("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=body,
                          headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read(16384))
        return (result.get("success") is True and result.get("hostname") == self.hostname
                and result.get("action") == action)
