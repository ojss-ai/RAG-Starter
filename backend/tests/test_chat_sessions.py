import uuid


async def _talk(client, headers, message, session_id=None):
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    r = await client.post("/api/v1/chat/stream", headers=headers, json=body)
    assert r.status_code == 200
    for block in r.text.split("\n\n"):
        if block.startswith("event: session"):
            import json
            return json.loads(block.split("\ndata: ", 1)[1])["session_id"]
    raise AssertionError("no session event in stream")


async def test_history_four_turns_then_clear(client, user_headers):
    sid = await _talk(client, user_headers, "first question")
    await _talk(client, user_headers, "second question", session_id=sid)

    r = await client.get(f"/api/v1/chat/history/{sid}", headers=user_headers)
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 4  # 2 user + 2 assistant
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]

    assert (await client.delete(f"/api/v1/chat/sessions/{sid}",
                                headers=user_headers)).status_code == 204
    assert (await client.get(f"/api/v1/chat/history/{sid}",
                             headers=user_headers)).status_code == 404


async def test_new_session_endpoint_and_listing(client, user_headers):
    r = await client.post("/api/v1/chat/sessions", headers=user_headers)
    assert r.status_code == 201
    sid = r.json()["id"]

    listed = await client.get("/api/v1/chat/sessions", headers=user_headers)
    assert sid in [s["id"] for s in listed.json()]


async def test_sessions_are_private_even_from_admin(client, user_headers, admin_headers):
    sid = await _talk(client, user_headers, "private question")
    assert (await client.get(f"/api/v1/chat/history/{sid}",
                             headers=admin_headers)).status_code == 404
    assert (await client.delete(f"/api/v1/chat/sessions/{sid}",
                                headers=admin_headers)).status_code == 404
    # unknown id also 404s (no existence oracle)
    assert (await client.get(f"/api/v1/chat/history/{uuid.uuid4()}",
                             headers=user_headers)).status_code == 404


async def test_endpoints_require_auth(client):
    assert (await client.get("/api/v1/chat/sessions")).status_code == 401
    assert (await client.post("/api/v1/chat/sessions")).status_code == 401
