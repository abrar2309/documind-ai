import uuid


def register(client, label):
    email = f"{label}-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Secure-Test-Password-2026!",
            "full_name": label,
        },
    )
    assert response.status_code == 201, response.text
    return email


def login(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "Secure-Test-Password-2026!",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_complete_workspace_rbac(client):
    owner_email = register(client, "Owner")
    admin_email = register(client, "Admin")
    second_admin_email = register(client, "SecondAdmin")
    member_email = register(client, "Member")
    viewer_email = register(client, "Viewer")
    outsider_email = register(client, "Outsider")

    owner = login(client, owner_email)
    admin = login(client, admin_email)
    second_admin = login(client, second_admin_email)
    member = login(client, member_email)
    viewer = login(client, viewer_email)
    outsider = login(client, outsider_email)

    workspace_response = client.post(
        "/api/v1/workspaces",
        headers=auth(owner),
        json={"name": "RBAC Integration Test"},
    )
    assert workspace_response.status_code == 201
    workspace_id = workspace_response.json()["id"]

    def add(email, role, token=owner):
        return client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            headers=auth(token),
            json={"email": email, "role": role},
        )

    assert add(admin_email, "admin").status_code == 201
    assert add(second_admin_email, "admin").status_code == 201
    assert add(member_email, "member").status_code == 201
    assert add(viewer_email, "viewer").status_code == 201

    # Owner can list workspace members.
    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=auth(owner),
    )
    assert response.status_code == 200
    assert len(response.json()) == 5

    # Admin can add ordinary members.
    new_member_email = register(client, "AdminAdded")
    assert add(new_member_email, "member", admin).status_code == 201

    # Admin cannot grant admin access.
    assert add(
        outsider_email, "admin", admin
    ).status_code == 403

    # Ordinary member cannot manage memberships.
    assert add(
        outsider_email, "member", member
    ).status_code == 403

    # Viewer cannot manage memberships.
    assert add(
        outsider_email, "member", viewer
    ).status_code == 403

    # Outsider cannot view workspace membership.
    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=auth(outsider),
    )
    assert response.status_code == 403

    # Admin cannot remove another admin.
    response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/"
        f"{client.get('/api/v1/users/me', headers=auth(second_admin)).json()['id']}",
        headers=auth(admin),
    )
    assert response.status_code == 403

    # Admin cannot remove the owner.
    owner_id = client.get(
        "/api/v1/users/me",
        headers=auth(owner),
    ).json()["id"]

    response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_id}",
        headers=auth(admin),
    )
    assert response.status_code == 400

    # Admin cannot promote a member to admin.
    member_id = client.get(
        "/api/v1/users/me",
        headers=auth(member),
    ).json()["id"]

    response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=auth(admin),
        json={"role": "admin"},
    )
    assert response.status_code == 403

    # Owner can update member role.
    response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=auth(owner),
        json={"role": "viewer"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"

    # Owner can remove an ordinary member.
    response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=auth(owner),
    )
    assert response.status_code == 204

    # Duplicate membership is rejected.
    assert add(admin_email, "member").status_code == 409

    # Invalid role is rejected by request validation.
    assert add(outsider_email, "superadmin").status_code == 422

    # Authentication is required.
    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/members"
    )
    assert response.status_code == 401
