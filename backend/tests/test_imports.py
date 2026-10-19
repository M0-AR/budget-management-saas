"""CSV transaction import contract tests (DB-backed).

Covers the happy path (mixed expenses/incomes, category auto-creation),
header aliases and date/amount formats, partial success with per-row
errors, duplicate skipping, header validation, role enforcement, the
row limit, and a full export → import round trip into a second tenant.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register_owner(client: AsyncClient, prefix: str) -> dict:
    slug = _slug(prefix)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": f"Workspace {prefix}",
            "tenant_slug": slug,
            "full_name": f"Owner {prefix}",
            "email": f"owner@{slug}.test",
            "password": "Passw0rd!x",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    body["slug"] = slug
    return body


async def _upload(
    client: AsyncClient,
    token: str,
    content: str,
    *,
    kind: str | None = None,
    skip_duplicates: bool | None = None,
):
    params: dict[str, str] = {}
    if kind is not None:
        params["kind"] = kind
    if skip_duplicates is not None:
        params["skip_duplicates"] = str(skip_duplicates).lower()
    return await client.post(
        "/api/v1/imports/transactions",
        files={"file": ("transactions.csv", content.encode(), "text/csv")},
        params=params,
        headers=_auth(token),
    )


async def test_import_happy_path_mixed(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "imp-a")
    token = owner["tokens"]["access_token"]

    # Registration seeds a default category set; reuse one and add a brand
    # new name so the import has to auto-create it.
    seeded = await db_client.get(
        "/api/v1/categories", params={"kind": "expense"}, headers=_auth(token)
    )
    by_name = {row["name"]: row for row in seeded.json()}
    assert "Groceries" in by_name
    groceries_id = by_name["Groceries"]["id"]
    new_name = f"Coffee-{uuid.uuid4().hex[:6]}"

    csv_body = (
        "date,type,category,note,amount\n"
        "2026-10-01,expense,Groceries,Weekly shop,120.50\n"
        f"2026-10-02,expense,{new_name},Latte,4.25\n"
        "2026-10-03,income,,Salary,2000\n"
    )
    response = await _upload(db_client, token, csv_body)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["imported_expenses"] == 2
    assert summary["imported_incomes"] == 1
    assert summary["duplicates_skipped"] == 0
    assert summary["failed"] == 0
    assert summary["categories_created"] == 1
    assert summary["errors"] == []

    expenses = await db_client.get(
        "/api/v1/expenses", params={"year": 2026, "month": 10}, headers=_auth(token)
    )
    assert expenses.status_code == 200
    items = expenses.json()["items"]
    assert expenses.json()["total"] == 2
    by_note = {item["note"]: item for item in items}
    assert by_note["Weekly shop"]["amount"] == 120.50
    assert by_note["Weekly shop"]["category_id"] == groceries_id
    assert by_note["Latte"]["category_name"] == new_name

    incomes = await db_client.get(
        "/api/v1/incomes", params={"year": 2026, "month": 10}, headers=_auth(token)
    )
    assert incomes.json()["total"] == 1
    assert incomes.json()["items"][0]["note"] == "Salary"

    categories = await db_client.get(
        "/api/v1/categories", params={"kind": "expense"}, headers=_auth(token)
    )
    assert new_name in [row["name"] for row in categories.json()]


async def test_import_aliases_and_formats(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "imp-b")
    token = owner["tokens"]["access_token"]

    csv_body = 'happened_on,description,total\n09/30/2026,"Lunch, later","$1,234.56"\n'
    response = await _upload(db_client, token, csv_body)
    assert response.status_code == 200, response.text
    assert response.json()["imported_expenses"] == 1

    expenses = await db_client.get(
        "/api/v1/expenses", params={"year": 2026, "month": 9}, headers=_auth(token)
    )
    item = expenses.json()["items"][0]
    assert item["amount"] == 1234.56
    assert item["note"] == "Lunch, later"
    assert item["happened_on"] == "2026-09-30"


async def test_import_partial_failure_reports_rows(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "imp-c")
    token = owner["tokens"]["access_token"]

    long_note = "x" * 501
    csv_body = (
        "date,amount,note\n"
        "2026-10-05,10,ok\n"
        "2026-13-45,10,bad date\n"
        "2026-10-06,-5,negative\n"
        f"2026-10-07,10,{long_note}\n"
    )
    response = await _upload(db_client, token, csv_body)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["imported_expenses"] == 1
    assert summary["failed"] == 3
    assert [error["row"] for error in summary["errors"]] == [3, 4, 5]
    assert "date" in summary["errors"][0]["message"]
    assert "positive" in summary["errors"][1]["message"]
    assert "500" in summary["errors"][2]["message"]


async def test_import_skips_duplicates(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "imp-d")
    token = owner["tokens"]["access_token"]

    csv_body = "date,amount,note\n2026-10-01,12.34,Coffee\n2026-10-02,5.00,Bus\n"
    first = await _upload(db_client, token, csv_body)
    assert first.json()["imported_expenses"] == 2

    again = await _upload(db_client, token, csv_body)
    assert again.json()["imported_expenses"] == 0
    assert again.json()["duplicates_skipped"] == 2

    forced = await _upload(db_client, token, csv_body, skip_duplicates=False)
    assert forced.json()["imported_expenses"] == 2
    assert forced.json()["duplicates_skipped"] == 0

    expenses = await db_client.get(
        "/api/v1/expenses", params={"year": 2026, "month": 10}, headers=_auth(token)
    )
    assert expenses.json()["total"] == 4


async def test_import_missing_columns(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "imp-e")
    token = owner["tokens"]["access_token"]

    response = await _upload(db_client, token, "foo,bar\n1,2\n")
    assert response.status_code == 422
    assert response.json()["code"] == "import_missing_columns"


async def test_import_row_limit(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "imp-f")
    token = owner["tokens"]["access_token"]

    csv_body = "date,amount,note\n" + "2026-10-01,1.00,row\n" * 1001
    response = await _upload(db_client, token, csv_body)
    assert response.status_code == 422
    assert response.json()["code"] == "import_too_many_rows"


async def test_import_requires_writer_role(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "imp-g")
    owner_token = owner["tokens"]["access_token"]

    email = f"viewer-{uuid.uuid4().hex[:8]}@{owner['slug']}.test"
    invite = await db_client.post(
        "/api/v1/members/invites",
        json={"email": email, "role": "viewer"},
        headers=_auth(owner_token),
    )
    assert invite.status_code == 201, invite.text
    joined = await db_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Viewer V",
            "email": email,
            "password": "Passw0rd!x",
            "invite_token": invite.json()["token"],
        },
    )
    assert joined.status_code == 201, joined.text
    viewer_token = joined.json()["tokens"]["access_token"]

    response = await _upload(db_client, viewer_token, "date,amount\n2026-10-01,1.00\n")
    assert response.status_code == 403


async def test_export_import_round_trip(db_client: AsyncClient) -> None:
    source = await _register_owner(db_client, "imp-h")
    source_token = source["tokens"]["access_token"]
    await db_client.post(
        "/api/v1/expenses",
        json={"amount": 33.33, "note": "Taxi", "happened_on": "2026-10-10"},
        headers=_auth(source_token),
    )
    await db_client.post(
        "/api/v1/incomes",
        json={"amount": 100.0, "note": "Gift", "happened_on": "2026-10-11"},
        headers=_auth(source_token),
    )
    exported = await db_client.get(
        "/api/v1/exports/transactions.csv",
        params={"year": 2026, "month": 10},
        headers=_auth(source_token),
    )
    assert exported.status_code == 200
    csv_text = exported.text
    assert "expense" in csv_text and "income" in csv_text

    target = await _register_owner(db_client, "imp-i")
    target_token = target["tokens"]["access_token"]
    imported = await _upload(db_client, target_token, csv_text)
    assert imported.status_code == 200, imported.text
    summary = imported.json()
    assert summary["imported_expenses"] == 1
    assert summary["imported_incomes"] == 1
    assert summary["failed"] == 0

    expenses = await db_client.get(
        "/api/v1/expenses", params={"year": 2026, "month": 10}, headers=_auth(target_token)
    )
    assert expenses.json()["total"] == 1
    assert expenses.json()["items"][0]["amount"] == 33.33
    incomes = await db_client.get(
        "/api/v1/incomes", params={"year": 2026, "month": 10}, headers=_auth(target_token)
    )
    assert incomes.json()["total"] == 1
    assert incomes.json()["items"][0]["note"] == "Gift"
