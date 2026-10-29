# Native AI rule-authoring authorization

Prepared October 29, 2026. Source and synthetic tests only; production activation is a separate approval.

`NEKTRON_MAIL_RULES_AUTHOR_ENABLED=true` adds the exact native scope `mail/rules.author` to the existing `/api/account/mail-native/session` endpoint. Missing or any other flag value leaves it disabled. Existing read/key and ingestion scopes, browser authorization, account-password checks, rate limits, and token signing are unchanged.

The Windows app asks for this authorization in its native NektronAI account dialog when the user chooses AI rule assistance. It creates a separate refresh family and protected device credential, bound to the same opaque shared account subject already signed in to Mail. It never upgrades a read/key or ingestion refresh family. Refresh retains the exact granted scope, and browser authorization remains read-only.

This scope authenticates the rule-authoring request. It grants no mailbox access, archive read, key recovery, database upload, sending, or automatic rule activation. The Mail rule-authoring endpoint must independently enforce the current paid `mail.ai_rules` entitlement. The account service does not grant subscriptions or infer mailbox ownership from an email address.

Authorization does not send message bodies to AI. Rule suggestions use the explicit prompt and supported editor fields; the client validates and presents the returned draft before the user applies it. Manual and already saved client rules remain independent of subscription or AI availability.

Disabling the issuer flag blocks new native authorizations, refresh, and profile lookup for this scope. Already issued short-lived access JWTs remain valid to a separately deployed verifier until expiry, so the rule API's own activation/entitlement checks remain authoritative for stopping use.

Synthetic verification: `tests/test_mail_rules_native.py`, alongside the existing native, read/key and ingestion authorization suites. No deployment, key rotation, production entitlement update, or live account sign-in is part of these source changes.
