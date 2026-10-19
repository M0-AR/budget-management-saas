#!/usr/bin/env bash
# End-to-end verification against a running stack (make up).
# Checks: health, tenant registration, login, tenant-scoped CRUD,
# and cross-tenant isolation (tenant B must never see tenant A's data).
set -euo pipefail

BASE="${BASE:-http://localhost}"

pass() { echo "  ✔ $1"; }
fail() { echo "  ✘ $1"; exit 1; }
jqget() { python3 -c "import json,sys,functools,operator; d=json.load(sys.stdin); print(functools.reduce(operator.getitem, sys.argv[1].split('/'), d))" "$1"; }

echo "== 1. Health =="
curl -fsS "$BASE/healthz" >/dev/null && pass "/healthz"
curl -fsS "$BASE/readyz" >/dev/null && pass "/readyz"

echo "== 2. Register two tenants =="
SLUG_A="e2e-a-$RANDOM"
SLUG_B="e2e-b-$RANDOM"
REG_A=$(curl -fsS -X POST "$BASE/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"tenant_name\":\"Acme A\",\"tenant_slug\":\"$SLUG_A\",\"full_name\":\"Alice A\",\"email\":\"alice@$SLUG_A.test\",\"password\":\"Passw0rd!a\"}")
echo "$REG_A" >/dev/null && pass "registered tenant A ($SLUG_A)"
TOKEN_A=$(echo "$REG_A" | jqget tokens/access_token)

REG_B=$(curl -fsS -X POST "$BASE/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"tenant_name\":\"Beta B\",\"tenant_slug\":\"$SLUG_B\",\"full_name\":\"Bob B\",\"email\":\"bob@$SLUG_B.test\",\"password\":\"Passw0rd!b\"}")
TOKEN_B=$(echo "$REG_B" | jqget tokens/access_token)
pass "registered tenant B ($SLUG_B)"

echo "== 3. Login =="
LOGIN=$(curl -fsS -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"tenant_slug\":\"$SLUG_A\",\"email\":\"alice@$SLUG_A.test\",\"password\":\"Passw0rd!a\"}")
TOKEN_A=$(echo "$LOGIN" | jqget tokens/access_token)
pass "login tenant A"

echo "== 4. Tenant A creates budget + expense =="
curl -fsS -X PUT "$BASE/api/v1/budgets" -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' \
  -d '{"year":2026,"month":10,"amount":3000,"alert_threshold_pct":80}' >/dev/null
pass "budget upsert"

CAT=$(curl -fsS -X POST "$BASE/api/v1/categories" -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' \
  -d '{"name":"E2E Groceries","kind":"expense","color":"#2f6df6"}')
CAT_ID=$(echo "$CAT" | jqget id)
pass "category create"

EXP=$(curl -fsS -X POST "$BASE/api/v1/expenses" -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' \
  -d "{\"amount\":42.5,\"category_id\":\"$CAT_ID\",\"note\":\"E2E test expense\",\"happened_on\":\"2026-10-18\"}")
EXP_ID=$(echo "$EXP" | jqget id)
pass "expense create ($EXP_ID)"

echo "== 5. Cross-tenant isolation =="
COUNT_B=$(curl -fsS "$BASE/api/v1/expenses" -H "Authorization: Bearer $TOKEN_B" | jqget total)
[ "$COUNT_B" = "0" ] && pass "tenant B sees 0 expenses" || fail "tenant B sees $COUNT_B expenses (LEAK!)"

CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/expenses/$EXP_ID" -H "Authorization: Bearer $TOKEN_B")
[ "$CODE" = "404" ] && pass "tenant B GET A's expense -> 404" || fail "tenant B got HTTP $CODE (expected 404)"

echo "== 6. Unauthenticated access rejected =="
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/expenses")
[ "$CODE" = "401" ] && pass "no token -> 401" || fail "no token got HTTP $CODE (expected 401)"

echo "== 7. Reports =="
curl -fsS "$BASE/api/v1/reports/dashboard" -H "Authorization: Bearer $TOKEN_A" >/dev/null && pass "dashboard report"
curl -fsS "$BASE/api/v1/reports/monthly?year=2026&month=10" -H "Authorization: Bearer $TOKEN_A" >/dev/null && pass "monthly report"

echo "== 8. CSV import =="
CSV_FILE=$(mktemp)
printf 'date,type,category,note,amount\n2026-10-02,expense,E2E Groceries,Imported shop,99.90\n2026-10-03,income,,Imported salary,1000\n' > "$CSV_FILE"
IMP=$(curl -fsS -X POST "$BASE/api/v1/imports/transactions?kind=expense" -H "Authorization: Bearer $TOKEN_A" -F "file=@$CSV_FILE;type=text/csv")
rm -f "$CSV_FILE"
[ "$(echo "$IMP" | jqget imported_expenses)" = "1" ] && pass "imported 1 expense row" || fail "imported_expenses != 1 ($IMP)"
[ "$(echo "$IMP" | jqget imported_incomes)" = "1" ] && pass "imported 1 income row" || fail "imported_incomes != 1 ($IMP)"
TOTAL_A=$(curl -fsS "$BASE/api/v1/expenses?year=2026&month=10" -H "Authorization: Bearer $TOKEN_A" | jqget total)
[ "$TOTAL_A" = "2" ] && pass "tenant A expenses = 2 after import" || fail "tenant A expenses = $TOTAL_A (expected 2)"

echo ""
echo "ALL E2E CHECKS PASSED ✔"
