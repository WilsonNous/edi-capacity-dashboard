"""Read-only MySQL connectivity probe. Run: python scripts/check_eddy_mysql.py.

Never prints passwords. Does not change database schema or EDDY_DB_ENGINE.
"""
from __future__ import annotations

import os
import sys

import pymysql


def main() -> int:
    required = ("EDDY_DB_HOST", "EDDY_DB_NAME", "EDDY_DB_USER", "EDDY_DB_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        print("MYSQL_CONFIG_MISSING:", ", ".join(missing))
        return 2

    mode = os.getenv("EDDY_DB_SSL_MODE", "REQUIRED").upper()
    if mode not in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"}:
        print("MYSQL_CONFIG_ERROR: unsupported EDDY_DB_SSL_MODE")
        return 2

    ca = os.getenv("EDDY_DB_SSL_CA")
    if mode in {"VERIFY_CA", "VERIFY_IDENTITY"} and not ca:
        print("MYSQL_CONFIG_ERROR: EDDY_DB_SSL_CA required for certificate verification")
        return 2

    kwargs = {
        "host": os.environ["EDDY_DB_HOST"],
        "port": int(os.getenv("EDDY_DB_PORT", "3306")),
        "user": os.environ["EDDY_DB_USER"],
        "password": os.environ["EDDY_DB_PASSWORD"],
        "database": os.environ["EDDY_DB_NAME"],
        "connect_timeout": 10,
        "read_timeout": 10,
        "write_timeout": 10,
        "ssl": {"ca": ca} if ca else {},
        "ssl_verify_cert": mode in {"VERIFY_CA", "VERIFY_IDENTITY"},
        "ssl_verify_identity": mode == "VERIFY_IDENTITY",
    }

    try:
        with pymysql.connect(**kwargs) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DATABASE(), CURRENT_USER()")
                database, account = cursor.fetchone()
                cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
                row = cursor.fetchone()
                cipher = row[1] if row else ""
                if not cipher:
                    print("MYSQL_TLS_NOT_ACTIVE")
                    return 1
                print("MYSQL_CONNECTION_OK")
                print("DATABASE:", database)
                print("ACCOUNT:", account)
                print("TLS_ACTIVE:", bool(cipher))
                print("TLS_CERT_VERIFIED:", mode in {"VERIFY_CA", "VERIFY_IDENTITY"})
        return 0
    except Exception as exc:
        # Driver exceptions may include connection parameters: never print exception text.
        print("MYSQL_CONNECTION_FAILED:", type(exc).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
