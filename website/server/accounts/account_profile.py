"""Shared signup profile validation and public country labels."""
import json
import re
import unicodedata
from pathlib import Path

COUNTRIES = json.loads((Path(__file__).resolve().parents[2] / "assets/account-countries.json").read_text(encoding="utf-8"))


def name(value, required=False):
    if not isinstance(value, str):
        raise ValueError("INVALID_NAME")
    value = value.strip()
    if required and not value:
        raise ValueError("NAME_REQUIRED")
    if len(value) > 100 or any(unicodedata.category(ch) in ("Cc", "Cs") for ch in value):
        raise ValueError("INVALID_NAME")
    if value and not any(ch.isalpha() for ch in value):
        raise ValueError("INVALID_NAME")
    return value


def signup_profile(data):
    first = name(data.get("firstName", ""), required=True)
    last = name(data.get("lastName", ""), required=True)
    middle = name(data.get("middleName", ""))
    country = data.get("countryCode")
    if not isinstance(country, str) or country not in COUNTRIES:
        raise ValueError("INVALID_COUNTRY")
    phone = data.get("phoneNumber", "")
    if not isinstance(phone, str):
        raise ValueError("INVALID_PHONE")
    phone = phone.strip()
    # Accept common international formatting; this is contact data, not verified MFA.
    if phone and (len(phone) > 30 or not re.fullmatch(r"\+?[0-9() .-]+", phone)
                  or not 4 <= sum(ch.isdigit() for ch in phone) <= 15):
        raise ValueError("INVALID_PHONE")
    return {"first_name": first, "last_name": last, "middle_name": middle,
            "country_code": country, "phone_number": phone}
