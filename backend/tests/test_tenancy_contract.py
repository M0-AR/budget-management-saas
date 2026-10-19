"""Cross-tenant isolation contract tests (DB-backed).

These are the "prove it" tests for the multi-tenant claim:
* API-level scoping,
* RLS at the database layer (asserted with raw SQL through the app role).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import SessionLocal, set_tenant_context


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
    body = response.json()
    body["slug"] = slug
    return body


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_cross_tenant_isolation_end_to_end(db_client: AsyncClient) -> None:
    tenant_a = await _register(db_client, "iso-a")
    tenant_b = await _register(db_client, "iso-b")
    token_a = tenant_a["tokens"]["access_token"]
    token_b = tenant_b["tokens"]["access_token"]

    # Tenant A creates a category and an expense.
    category_response = await db_client.post(
        "/api/v1/categories",
        json={"name": "A-only category", "kind": "expense", "color": "#112233"},
        headers=_auth(token_a),
    )
    assert category_response.status_code == 201, category_response.text
    category_id = category_response.json()["id"]

    expense_response = await db_client.post(
        "/api/v1/expenses",
        json={
            "amount": 123.45,
            "category_id": category_id,
            "note": "A private expense",
            "happened_on": "2026-10-15",
        },
        headers=_auth(token_a),
    )
    assert expense_response.status_code == 201, expense_response.text
    expense_id = expense_response.json()["id"]

    # Tenant B must not see any of it.
    listing = await db_client.get("/api/v1/expenses", headers=_auth(token_b))
    assert listing.status_code == 200
    assert listing.json()["total"] == 0

    direct = await db_client.get(f"/api/v1/expenses/{expense_id}", headers=_auth(token_b))
    assert direct.status_code == 404

    update = await db_client.put(
        f"/api/v1/expenses/{expense_id}", json={"amount": 1.0}, headers=_auth(token_b)
    )
    assert update.status_code == 404

    delete = await db_client.delete(f"/api/v1/expenses/{expense_id}", headers=_auth(token_b))
    assert delete.status_code == 404

    categories_b = await db_client.get("/api/v1/categories", headers=_auth(token_b))
    names_b = {item["name"] for item in categories_b.json()}
    assert "A-only category" not in names_b

    # Tenant B cannot attach a foreign category id (would fail validation).
    foreign_category = await db_client.post(
        "/api/v1/expenses",
        json={
            "amount": 5.0,
            "category_id": category_id,
            "note": "cross-tenant category attempt",
            "happened_on": "2026-10-15",
        },
        headers=_auth(token_b),
    )
    assert foreign_category.status_code == 422


async def test_rls_backstop_blocks_raw_cross_tenant_reads(db_client: AsyncClient) -> None:
    """Even without any application-level filter, RLS returns zero rows."""
    tenant_a = await _register(db_client, "rls-a")
    tenant_b = await _register(db_client, "rls-b")

    created = await db_client.post(
        "/api/v1/expenses",
        json={"amount": 77.7, "note": "RLS probe", "happened_on": "2026-10-16"},
        headers=_auth(tenant_a["tokens"]["access_token"]),
    )
    assert created.status_code == 201, created.text
    expense_id = created.json()["id"]

    tenant_a_id = uuid.UUID(tenant_a["user"]["tenant_id"])
    tenant_b_id = uuid.UUID(tenant_b["user"]["tenant_id"])

    async with SessionLocal() as session:
        async with session.begin():
            # Pin tenant B, then run raw SQL with NO tenant filter at all.
            await set_tenant_context(session, tenant_b_id)
            rows = (
                await session.execute(
                    text("SELECT id FROM expenses WHERE id = :id"), {"id": expense_id}
                )
            ).all()
            assert rows == []

            # Sanity: tenant A (the owner of the row) does see it.
            await set_tenant_context(session, tenant_a_id)
            rows = (
                await session.execute(
                    text("SELECT id FROM expenses WHERE id = :id"), {"id": expense_id}
                )
            ).all()
            assert len(rows) == 1


async def test_no_tenant_context_means_no_rows(db_client: AsyncClient) -> None:
    await _register(db_client, "ctx-a")

    async with SessionLocal() as session:
        async with session.begin():
            rows = (await session.execute(text("SELECT id FROM expenses"))).all()
            assert rows == []
            # Writes without context are rejected by the WITH CHECK clause.
            with pytest.raises(Exception):
                await session.execute(
                    text(
                        "INSERT INTO expenses (id, tenant_id, amount, note, happened_on) "
                        "VALUES (gen_random_uuid(), gen_random_uuid(), 1, 'x', now())"
                    )
                )


async def test_login_scoping_and_bad_credentials(db_client: AsyncClient) -> None:
    tenant = await _register(db_client, "login")
    slug = tenant["slug"]

    # Wrong workspace slug -> 401 (not 404: no workspace enumeration).
    missing = await db_client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": _random_slug("nope"), "email": "owner@x.test", "password": "Passw0rd!x"},
    )
    assert missing.status_code == 401

    # Correct slug, wrong password -> 401.
    wrong = await db_client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner@{slug}.test", "password": "wrong-password"},
    )
    assert wrong.status_code == 401

    # Identical email exists in another workspace but is NOT visible here.
    other = await _register(db_client, "login2")
    cross = await db_client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner@{other['slug']}.test", "password": "Passw0rd!x"},
    )
    assert cross.status_code == 401

    ok = await db_client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner@{slug}.test", "password": "Passw0rd!x"},
    )
    assert ok.status_code == 200
    assert ok.json()["user"]["role"] == "owner"


async def test_duplicate_slug_conflict(db_client: AsyncClient) -> None:
    tenant = await _register(db_client, "dupe")
    again = await db_client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Another",
            "tenant_slug": tenant["slug"],
            "full_name": "Someone",
            "email": "someone@example.test",
            "password": "Passw0rd!x",
        },
    )
    assert again.status_code == 409


async def test_reports_are_tenant_scoped(db_client: AsyncClient) -> None:
    tenant_a = await _register(db_client, "rep-a")
    tenant_b = await _register(db_client, "rep-b")
    token_a = tenant_a["tokens"]["access_token"]
    token_b = tenant_b["tokens"]["access_token"]

    await db_client.put(
        "/api/v1/budgets",
        json={"year": 2026, "month": 10, "amount": 1000},
        headers=_auth(token_a),
    )
    await db_client.post(
        "/api/v1/expenses",
        json={"amount": 400.0, "note": "report probe", "happened_on": "2026-10-10"},
        headers=_auth(token_a),
    )

    dashboard_a = (
        await db_client.get("/api/v1/reports/dashboard?year=2026&month=10", headers=_auth(token_a))
    ).json()
    assert dashboard_a["budget_amount"] == 1000.0
    assert dashboard_a["expense_total"] == 400.0
    assert dashboard_a["status"] == "on_track"

    dashboard_b = (
        await db_client.get("/api/v1/reports/dashboard?year=2026&month=10", headers=_auth(token_b))
    ).json()
    assert dashboard_b["budget_amount"] == 0.0
    assert dashboard_b["expense_total"] == 0.0
    assert dashboard_b["status"] == "no_budget"


async def test_refresh_rotation_and_branding_public(db_client: AsyncClient) -> None:
    tenant = await _register(db_client, "rot")
    tokens = tenant["tokens"]

    refreshed = await db_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    rotated = refreshed.json()
    assert rotated["access_token"]
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # Replaying an already-rotated token is treated as theft: 401 and the
    # whole family — including the fresh successor — is revoked.
    replay = await db_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401

    successor = await db_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert successor.status_code == 401

    # A refresh token is not accepted as an access token.
    as_access = await db_client.get(
        "/api/v1/auth/me", headers=_auth(tokens["refresh_token"])
    )
    assert as_access.status_code == 401

    public = await db_client.get(f"/api/v1/settings/public/{tenant['slug']}")
    assert public.status_code == 200
    body = public.json()
    assert body["slug"] == tenant["slug"]
    assert "branding" not in body  # only safe fields are exposed


async def test_logout_revokes_refresh_family(db_client: AsyncClient) -> None:
    tenant = await _register(db_client, "logout")
    refresh_token = tenant["tokens"]["refresh_token"]

    logged_out = await db_client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert logged_out.status_code == 204

    after = await db_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert after.status_code == 401


async def test_refresh_cookie_is_httponly_and_scoped(db_client: AsyncClient) -> None:
    tenant = await _register(db_client, "cookie")

    response = await db_client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": tenant["slug"],
            "email": f"owner@{tenant['slug']}.test",
            "password": "Passw0rd!x",
        },
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "bms_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie
