"""Regression tests for transaction updates.

An update whose audit detail contained a UUID (for example ``category_id``)
used to fail JSON encoding at commit time: the endpoint returned 200 with the
new values, then the transaction was rolled back silently. These tests assert
the edit actually survives a follow-up read.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient


def _random_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


async def _register(client: AsyncClient, prefix: str) -> dict:
    slug = _random_slug(prefix)
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
    return response.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_expense_update_with_category_persists(db_client: AsyncClient) -> None:
    account = await _register(db_client, "edit-expense")
    headers = _auth(account["tokens"]["access_token"])

    categories = await db_client.get("/api/v1/categories?kind=expense", headers=headers)
    assert categories.status_code == 200
    category_id = categories.json()[0]["id"]

    created = await db_client.post(
        "/api/v1/expenses",
        json={
            "amount": 10.0,
            "category_id": category_id,
            "note": "before",
            "happened_on": "2026-10-19",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    expense_id = created.json()["id"]

    updated = await db_client.put(
        f"/api/v1/expenses/{expense_id}",
        json={
            "amount": 42.5,
            "category_id": category_id,
            "note": "after",
            "happened_on": "2026-10-19",
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["amount"] == 42.5

    fetched = await db_client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["amount"] == 42.5
    assert body["note"] == "after"
    assert body["category_id"] == category_id


async def test_income_update_with_category_persists(db_client: AsyncClient) -> None:
    account = await _register(db_client, "edit-income")
    headers = _auth(account["tokens"]["access_token"])

    categories = await db_client.get("/api/v1/categories?kind=income", headers=headers)
    assert categories.status_code == 200
    category_id = categories.json()[0]["id"]

    created = await db_client.post(
        "/api/v1/incomes",
        json={
            "amount": 100.0,
            "category_id": category_id,
            "note": "before",
            "happened_on": "2026-10-19",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    income_id = created.json()["id"]

    updated = await db_client.put(
        f"/api/v1/incomes/{income_id}",
        json={
            "amount": 250.0,
            "category_id": category_id,
            "note": "after",
            "happened_on": "2026-10-19",
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text

    fetched = await db_client.get(f"/api/v1/incomes/{income_id}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["amount"] == 250.0
    assert body["note"] == "after"
    assert body["category_id"] == category_id
