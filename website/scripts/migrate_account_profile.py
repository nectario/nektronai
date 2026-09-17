"""Add nullable User.CountryCode without altering existing accounts or credentials."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server/accounts"))
from store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the additive, idempotent schema migration")
    args = parser.parse_args()
    settings = {k: v for k, v in os.environ.items() if k.startswith("NEKTRON_DB_")}
    settings["NEKTRON_DB_CA_FILE"] = str(ROOT / "server/accounts/rds-ca.pem")
    store = Store(settings)
    with store.connection() as connection, connection.cursor() as cur:
        cur.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='User'")
        columns = {row["COLUMN_NAME"] for row in cur.fetchall()}
        if not {"UserId", "FirstName", "LastName", "MiddleName", "PhoneNumber"} <= columns:
            raise RuntimeError("Expected existing User profile columns are missing")
    print("Profile schema preflight passed. CountryCode present: " + str("CountryCode" in columns))
    if args.apply:
        store.migrate_profile()
        print("CountryCode is ready. Existing account data was not changed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Profile schema migration failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
