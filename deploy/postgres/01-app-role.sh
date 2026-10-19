#!/bin/sh
# Creates the non-superuser role the application (and Alembic) run as.
# Postgres superusers bypass Row-Level Security, so the app must never
# connect as POSTGRES_USER — this role exists to make RLS a real boundary.
set -eu

APP_USER="${APP_DB_USER:-budget_app}"
APP_PASSWORD="${APP_DB_PASSWORD:-$POSTGRES_PASSWORD}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE ${APP_USER} LOGIN PASSWORD '${APP_PASSWORD}';
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${APP_USER};
    GRANT USAGE, CREATE ON SCHEMA public TO ${APP_USER};
EOSQL
