#!/bin/sh
# Wait for Postgres, apply migrations, then serve (or exec the given command).
set -e

wait_for_db() {
	python - <<'PY'
import asyncio
import os
import sys

import asyncpg


async def main() -> None:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    last_error: Exception | None = None
    for attempt in range(60):
        try:
            connection = await asyncpg.connect(dsn=dsn, timeout=3)
            await connection.close()
            print("database is reachable")
            return
        except Exception as exc:  # noqa: BLE001 - startup retry loop
            last_error = exc
            print(f"waiting for database ({attempt + 1}/60): {exc}", flush=True)
            await asyncio.sleep(2)
    sys.exit(f"database did not become reachable: {last_error}")


asyncio.run(main())
PY
}

case "${1:-serve}" in
serve)
	wait_for_db
	alembic upgrade head
	exec uvicorn app.main:app \
		--host 0.0.0.0 \
		--port 8000 \
		--proxy-headers \
		--forwarded-allow-ips "*" \
		--workers "${WEB_CONCURRENCY:-1}"
	;;
*)
	exec "$@"
	;;
esac
