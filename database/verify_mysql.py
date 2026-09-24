"""Phase 0 check: connect to MySQL with the .env credentials and run SELECT 1."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymysql  # noqa: E402

from config import settings  # noqa: E402


def main() -> int:
    conn = pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1, VERSION(), DATABASE(), CURRENT_USER()")
            one, version, db, user = cur.fetchone()
    finally:
        conn.close()

    print(f"SELECT 1 -> {one} | MySQL {version} | database={db} | user={user}")
    if one != 1:
        print("VERIFY_MYSQL: FAIL")
        return 1
    print("VERIFY_MYSQL: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
