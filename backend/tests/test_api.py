import pytest

from ml import config as ml_config
from ml import preprocessing

CONSENT = "2026-11-v1"


@pytest.fixture(scope="module")
def real_minutes():
    """Real per-minute rows from the SWELL-KW data, renamed to the API field names."""
    data = preprocessing.load_minute_data()
    person = data[data.participant == "3"].sort_values(["block", "ts"])
    rows = []
    for _, row in person.iterrows():
        rows.append({field: float(row[field]) for field in ml_config.MINUTE_FIELDS})
    return rows


def start(client, headers):
    response = client.post("/api/sessions/start", json={"consent": True, "consent_version": CONSENT}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def test_health_and_model_info(client):
    assert client.get("/api/health").json()["model_loaded"] is True
    info = client.get("/api/model/info").json()
    assert info["models"]["stress"]["target"] == "stress_elevated"
    assert info["models"]["workload"]["reliable_signal"] is False   # honest flag from LOSO evaluation


def test_consent_is_required(client, headers):
    refused = client.post("/api/sessions/start", json={"consent": False, "consent_version": CONSENT}, headers=headers)
    assert refused.status_code == 400
    missing_field = client.post("/api/sessions/start", json={}, headers=headers)
    assert missing_field.status_code == 422
    no_client = client.post("/api/sessions/start", json={"consent": True, "consent_version": CONSENT})
    assert no_client.status_code == 401
    old_version = client.post("/api/sessions/start", json={"consent": True, "consent_version": "old-version"}, headers=headers)
    assert old_version.status_code == 400


def test_full_session_flow_with_real_model(client, headers, real_minutes):
    session_id = start(client, headers)
    statuses = []
    last = None
    for minute in real_minutes[:20]:
        response = client.post("/api/sessions/" + session_id + "/metrics", json=minute, headers=headers)
        assert response.status_code == 200, response.text
        last = response.json()
        statuses.append(last["estimate"]["status"])

    assert statuses[0] == "insufficient_data"
    assert "calibrating" in statuses
    assert statuses[-1] == "ok"
    stress = last["estimate"]["stress"]
    assert 0.0 <= stress["score"] <= 1.0
    assert stress["leaning"] in ("higher_than_usual", "lower_than_usual", "unclear")
    assert last["estimate"]["baseline_source"] == "this_session_provisional"
    assert len(stress["contributions"]) == 5
    assert last["estimate"]["workload"]["reliable"] is False
    assert "diagnosis" in last["estimate"]["disclaimer"].lower()

    stopped = client.post("/api/sessions/" + session_id + "/stop", headers=headers).json()
    assert stopped["status"] == "stopped"
    assert stopped["minutes_recorded"] == 20

    analytics = client.get("/api/sessions/" + session_id + "/analytics", headers=headers).json()
    assert len(analytics["series"]) == 20
    assert analytics["pattern_changes"] is not None
    assert "typing_cv" in analytics["variability"]
    assert len(analytics["estimate_history"]) > 0

    # second session now has a baseline from the first one
    second = client.post("/api/sessions/start", json={"consent": True, "consent_version": CONSENT}, headers=headers).json()
    assert second["baseline_available"] is True
    for minute in real_minutes[20:30]:
        result = client.post("/api/sessions/" + second["session_id"] + "/metrics", json=minute, headers=headers).json()
    assert result["estimate"]["baseline_source"] == "previous_sessions"
    comparison = client.get("/api/sessions/" + second["session_id"] + "/analytics", headers=headers).json()
    assert comparison["versus_baseline"] is not None

    sessions = client.get("/api/sessions", headers=headers).json()
    assert len(sessions) == 2
    overview = client.get("/api/overview", headers=headers).json()
    assert overview["session_count"] == 2


def test_sessions_are_private_to_their_client(client, headers):
    session_id = start(client, headers)
    other = {"X-Client-Id": "client_someone_else_0000"}
    assert client.get("/api/sessions/" + session_id, headers=other).status_code == 404
    assert client.post("/api/sessions/" + session_id + "/stop", headers=other).status_code == 404
    assert client.get("/api/sessions", headers=other).json() == []


def test_typed_text_or_unknown_fields_are_rejected(client, headers):
    session_id = start(client, headers)
    payload = {"keystrokes": 10, "typed_text": "my password is hunter2"}
    response = client.post("/api/sessions/" + session_id + "/metrics", json=payload, headers=headers)
    assert response.status_code == 422
    negative = client.post("/api/sessions/" + session_id + "/metrics", json={"keystrokes": -5}, headers=headers)
    assert negative.status_code == 422
    huge = client.post("/api/sessions/" + session_id + "/metrics", json={"keystrokes": 10**7}, headers=headers)
    assert huge.status_code == 422


def test_cannot_post_to_stopped_session(client, headers):
    session_id = start(client, headers)
    client.post("/api/sessions/" + session_id + "/stop", headers=headers)
    response = client.post("/api/sessions/" + session_id + "/metrics", json={"keystrokes": 5}, headers=headers)
    assert response.status_code == 409


def test_websocket_live_updates(client, headers, real_minutes):
    session_id = start(client, headers)
    client_id = headers["X-Client-Id"]
    with client.websocket_connect("/ws/sessions/" + session_id + "?client_id=" + client_id) as websocket:
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json()["type"] == "pong"

        # metrics sent over the socket itself
        websocket.send_json({"type": "metrics", "data": real_minutes[0]})
        message = websocket.receive_json()
        assert message["type"] == "update"
        assert message["minute_index"] == 0

        # metrics sent by REST are pushed to the socket
        client.post("/api/sessions/" + session_id + "/metrics", json=real_minutes[1], headers=headers)
        assert websocket.receive_json()["minute_index"] == 1

        websocket.send_json({"type": "metrics", "data": {"keystrokes": 1, "text": "secret"}})
        assert websocket.receive_json()["type"] == "error"


def test_websocket_rejects_wrong_owner(client, headers):
    from starlette.websockets import WebSocketDisconnect
    session_id = start(client, headers)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/sessions/" + session_id + "?client_id=client_intruder_000000") as websocket:
            websocket.receive_json()


def test_delete_my_data(client, headers):
    start(client, headers)
    assert client.delete("/api/data", headers=headers).status_code == 204
    assert client.get("/api/sessions", headers=headers).json() == []
