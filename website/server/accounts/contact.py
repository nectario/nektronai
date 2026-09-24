"""Bounded, plain-text contact submissions. No uploads, URL fetching or message storage."""
import unicodedata
from flask import jsonify, request
from email_validator import validate_email

TOPICS = {'general': 'General inquiry', 'research': 'Research', 'products': 'Products', 'support': 'Product support'}


def field(value, maximum, multiline=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError('INVALID_INPUT')
    if any(unicodedata.category(c) in ('Cc', 'Cs') and not (multiline and c in '\n\r\t') for c in value):
        raise ValueError('INVALID_INPUT')
    return value.strip()


def register_contact(app, store, mailer):
    @app.post('/api/account/contact')
    def contact():
        # Origin, CSRF, JSON content type and 4 KiB request bounds are enforced by app/nginx.
        ip = request.remote_addr or 'unknown'
        if not store.allow_request('contact:attempt:' + ip, limit=10, seconds=3600):
            return jsonify(error='TRY_LATER'), 429
        try:
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or set(data) - {'name', 'email', 'topic', 'message', 'website'}:
                raise ValueError('INVALID_INPUT')
            honeypot = field(data.get('website', ''), 200)
            name = field(data.get('name'), 100)
            email = validate_email(field(data.get('email'), 254), check_deliverability=False,
                                   allow_smtputf8=False).ascii_email.lower()
            topic = field(data.get('topic'), 20)
            message = field(data.get('message'), 2000, multiline=True)
            if not name or topic not in TOPICS or len(message) < 10:
                raise ValueError('INVALID_INPUT')
        except ValueError:
            return jsonify(error='INVALID_INPUT'), 400
        if honeypot:
            return jsonify(sent=True)
        limits = [('contact:ip:' + ip, 3, 3600), ('contact:email:' + email, 3, 3600),
                  ('contact:cooldown:' + ip, 1, 60), ('contact:global', 30, 3600)]
        for key, limit, seconds in limits:
            if not store.allow_request(key, limit=limit, seconds=seconds):
                return jsonify(error='TRY_LATER'), 429
        try:
            mailer.send_contact(name, email, TOPICS[topic], message)
        except Exception as error:
            # Never put user-submitted text, addresses or credentials into logs.
            app.logger.error('contact_delivery_failed type=%s', type(error).__name__)
            return jsonify(error='CONTACT_UNAVAILABLE'), 503
        return jsonify(sent=True)
