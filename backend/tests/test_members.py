"""Workspace member + invitation contract tests (DB-backed).

Covers the role-management guardrails (no self-changes, owner immutable,
admin reach), the invite lifecycle (create → list → accept → single-use),
email binding, and the isolation of member management across tenants.
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


async def _invite_and_join(
    client: AsyncClient, owner_token: str, owner_body: dict, *, role: str = "member", name: str = "Joiner"
) -> dict:
    email = f"joiner-{uuid.uuid4().hex[:8]}@{owner_body['slug']}.test"
    invite = await client.post(
        "/api/v1/members/invites",
        json={"email": email, "role": role},
        headers=_auth(owner_token),
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["token"]

    joined = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": "Passw0rd!x",
            "invite_token": token,
        },
    )
    assert joined.status_code == 201, joined.text
    body = joined.json()
    body["email"] = email
    body["invite_token"] = token
    return body


async def test_invite_lifecycle(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "mem-a")
    token = owner["tokens"]["access_token"]

    # Create + list.
    email = f"newbie@{owner['slug']}.test"
    created = await db_client.post(
        "/api/v1/members/invites", json={"email": email, "role": "member"}, headers=_auth(token)
    )
    assert created.status_code == 201, created.text
    invite = created.json()
    assert invite["email"] == email
    assert len(invite["token"]) > 20

    pending = await db_client.get("/api/v1/members/invites", headers=_auth(token))
    assert pending.status_code == 200
    assert [row["email"] for row in pending.json()] == [email]

    # Duplicate pending invite is rejected.
    duplicate = await db_client.post(
        "/api/v1/members/invites", json={"email": email, "role": "viewer"}, headers=_auth(token)
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "invite_pending"

    # Accept.
    joined = await db_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "New Bie",
            "email": email,
            "password": "Passw0rd!x",
            "invite_token": invite["token"],
        },
    )
    assert joined.status_code == 201, joined.text
    body = joined.json()
    assert body["user"]["role"] == "member"
    assert body["tenant"]["slug"] == owner["slug"]

    # Now a member: invite for that email is refused, invite is gone from list.
    member_token = body["tokens"]["access_token"]
    as_member = await db_client.post(
        "/api/v1/members/invites", json={"email": email, "role": "member"}, headers=_auth(member_token)
    )
    assert as_member.status_code == 403
    assert (await db_client.get("/api/v1/members/invites", headers=_auth(token))).json() == []

    already = await db_client.post(
        "/api/v1/members/invites", json={"email": email, "role": "member"}, headers=_auth(token)
    )
    assert already.status_code == 409
    assert already.json()["code"] == "already_member"

    # Single use: replaying the token fails.
    replay = await db_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Impostor",
            "email": f"other@{owner['slug']}.test",
            "password": "Passw0rd!x",
            "invite_token": invite["token"],
        },
    )
    assert replay.status_code == 422

    # Members list: both visible to each other.
    listing = await db_client.get("/api/v1/members", headers=_auth(member_token))
    assert listing.status_code == 200
    roles = {row["email"]: row["role"] for row in listing.json()}
    assert roles[owner["user"]["email"]] == "owner"
    assert roles[email] == "member"


async def test_invite_is_email_bound(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "mem-b")
    token = owner["tokens"]["access_token"]
    created = await db_client.post(
        "/api/v1/members/invites",
        json={"email": f"intended@{owner['slug']}.test", "role": "member"},
        headers=_auth(token),
    )
    invite_token = created.json()["token"]

    wrong = await db_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Wrong Email",
            "email": f"someone-else@{owner['slug']}.test",
            "password": "Passw0rd!x",
            "invite_token": invite_token,
        },
    )
    assert wrong.status_code == 422
    assert wrong.json()["code"] == "invite_email_mismatch"


async def test_invite_revoke_and_invalid_token(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "mem-c")
    token = owner["tokens"]["access_token"]
    created = await db_client.post(
        "/api/v1/members/invites",
        json={"email": f"revoked@{owner['slug']}.test", "role": "viewer"},
        headers=_auth(token),
    )
    invite = created.json()

    revoked = await db_client.delete(f"/api/v1/members/invites/{invite['id']}", headers=_auth(token))
    assert revoked.status_code == 204

    after = await db_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Too Late",
            "email": invite["email"],
            "password": "Passw0rd!x",
            "invite_token": invite["token"],
        },
    )
    assert after.status_code == 422

    garbage = await db_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Garbage Token",
            "email": f"x@{owner['slug']}.test",
            "password": "Passw0rd!x",
            "invite_token": "not-a-real-invite-token-at-all",
        },
    )
    assert garbage.status_code == 422


async def test_role_management_guardrails(db_client: AsyncClient) -> None:
    owner = await _register_owner(db_client, "mem-d")
    owner_token = owner["tokens"]["access_token"]
    admin = await _invite_and_join(db_client, owner_token, owner, role="admin")
    admin_token = admin["tokens"]["access_token"]
    member = await _invite_and_join(db_client, owner_token, owner, role="member", name="Mia Member")
    member_token = member["tokens"]["access_token"]

    # A member cannot manage anyone.
    forbidden = await db_client.patch(
        f"/api/v1/members/{admin['user']['id']}", json={"role": "viewer"}, headers=_auth(member_token)
    )
    assert forbidden.status_code == 403

    # The owner cannot be re-roled or removed.
    owner_target = await db_client.patch(
        f"/api/v1/members/{owner['user']['id']}", json={"role": "admin"}, headers=_auth(admin_token)
    )
    assert owner_target.status_code == 403
    owner_remove = await db_client.delete(
        f"/api/v1/members/{owner['user']['id']}", headers=_auth(admin_token)
    )
    assert owner_remove.status_code == 403

    # Nobody changes themselves (even the owner).
    self_change = await db_client.patch(
        f"/api/v1/members/{owner['user']['id']}", json={"role": "member"}, headers=_auth(owner_token)
    )
    assert self_change.status_code == 403

    # An admin may not manage a peer admin.
    other_admin = await _invite_and_join(db_client, owner_token, owner, role="admin", name="Ada Admin")
    peer = await db_client.patch(
        f"/api/v1/members/{other_admin['user']['id']}",
        json={"role": "member"},
        headers=_auth(admin_token),
    )
    assert peer.status_code == 403

    # An admin can manage members and viewers.
    demote = await db_client.patch(
        f"/api/v1/members/{member['user']['id']}", json={"role": "viewer"}, headers=_auth(admin_token)
    )
    assert demote.status_code == 200
    assert demote.json()["role"] == "viewer"

    # Owner may manage admins.
    owner_demote = await db_client.patch(
        f"/api/v1/members/{other_admin['user']['id']}", json={"role": "member"}, headers=_auth(owner_token)
    )
    assert owner_demote.status_code == 200

    # Removing a viewer works; their tokens die with the row.
    removed = await db_client.delete(
        f"/api/v1/members/{member['user']['id']}", headers=_auth(owner_token)
    )
    assert removed.status_code == 204
    stale = await db_client.get("/api/v1/members", headers=_auth(member_token))
    assert stale.status_code == 401
    stale_refresh = await db_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": member["tokens"]["refresh_token"]}
    )
    assert stale_refresh.status_code == 401

    # Self-removal is forbidden.
    self_remove = await db_client.delete(
        f"/api/v1/members/{admin['user']['id']}", headers=_auth(admin_token)
    )
    assert self_remove.status_code == 403


async def test_member_management_is_tenant_scoped(db_client: AsyncClient) -> None:
    tenant_a = await _register_owner(db_client, "mem-e")
    tenant_b = await _register_owner(db_client, "mem-f")
    token_a = tenant_a["tokens"]["access_token"]
    token_b = tenant_b["tokens"]["access_token"]

    joined_a = await _invite_and_join(db_client, token_a, tenant_a)

    # B cannot see A's members, nor touch them.
    listing_b = await db_client.get("/api/v1/members", headers=_auth(token_b))
    assert [row["email"] for row in listing_b.json()] == [tenant_b["user"]["email"]]

    cross_patch = await db_client.patch(
        f"/api/v1/members/{joined_a['user']['id']}", json={"role": "viewer"}, headers=_auth(token_b)
    )
    assert cross_patch.status_code == 404
    cross_remove = await db_client.delete(
        f"/api/v1/members/{joined_a['user']['id']}", headers=_auth(token_b)
    )
    assert cross_remove.status_code == 404

    # B cannot revoke A's invite either.
    created = await db_client.post(
        "/api/v1/members/invites",
        json={"email": f"pa@{tenant_a['slug']}.test", "role": "member"},
        headers=_auth(token_a),
    )
    assert created.status_code == 201
    cross_revoke = await db_client.delete(
        f"/api/v1/members/invites/{created.json()['id']}", headers=_auth(token_b)
    )
    assert cross_revoke.status_code == 404

    # The same email can join a second workspace independently.
    same_email = joined_a["email"]
    invite_b = await db_client.post(
        "/api/v1/members/invites",
        json={"email": same_email, "role": "viewer"},
        headers=_auth(token_b),
    )
    assert invite_b.status_code == 201
    joined_b = await db_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Multi Workspace",
            "email": same_email,
            "password": "Passw0rd!x",
            "invite_token": invite_b.json()["token"],
        },
    )
    assert joined_b.status_code == 201, joined_b.text
    assert joined_b.json()["tenant"]["slug"] == tenant_b["slug"]
    assert joined_b.json()["user"]["role"] == "viewer"


async def test_workspace_fields_still_required_without_invite(db_client: AsyncClient) -> None:
    response = await db_client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Workspace", "email": "nw@example.test", "password": "Passw0rd!x"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "workspace_required"
