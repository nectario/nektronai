# Public contact form

`contact.html` posts JSON to `/api/account/contact` on the existing loopback-only
Flask service. No new database privileges, tables, public function URLs or secrets
are needed. The existing SES permission for info@nektron.ai is reused.

- The page is public; login is not required. Exact Origin, a server-side CSRF
  token, a first-party secure cookie and JSON are required for submission.
- nginx and Flask enforce a 4 KiB request limit. The server validates field types,
  allowed keys/topics, lengths, single-address email syntax and control characters.
- Messages are plain-text email only. No message HTML is rendered or executed,
  no SQL is built from form values, no URL is fetched, and no file is accepted.
- Recipient is fixed to info@nektron.ai; the verified sender stays NektronAI.
  Only the validated visitor email becomes Reply-To. No autoresponder is sent.
- Database-backed limits: ten attempts/IP/hour, three sends/IP/hour and per-email/hour,
  one send/IP/minute window, and thirty sends/site/hour. Failures count toward limits.
  A honeypot drops obvious automated submissions without delivering mail.
- Requests fail closed if rate-limit storage is unavailable. Delivery failures
  return a generic error, not a success. Logs contain error class only, not messages.
- The form keeps entered text on errors. It prevents double clicks while sending.
  Delivery retries/timeouts can still produce duplicates; this is not exactly-once delivery.
- Messages reside in the destination mailbox, not a website message table. The
  privacy notice describes the submitted information and its response purpose.
- Contact-only CSP, frame denial and no-referrer/nosniff headers reduce browser
  attack surfaces; the remaining pages keep their existing styling and behavior.

No public form is attack-proof. CSRF and a honeypot are not proof of humanity.
Distributed spam remains possible within the global cap. Monitor
`contact_delivery_failed` and HTTP 429/5xx counts. If abuse grows, add a verified
server-side CAPTCHA or WAF rule before raising limits; never trust client-only checks.
Treat incoming messages and links as untrusted, including in any downstream AI workflows.

Tests: `python -m unittest discover -s website/server/accounts/tests -v` and
`node website/tests/contact_browser.cjs` (local preview on port 8771, mocked API).
