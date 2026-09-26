from c1_awards.api_discovery import (
    _replay_headers,
    _safe_session_cookies,
    redact_headers,
    score_candidate,
)


def test_redact_headers_hides_session_material():
    headers = {
        "authorization": "Bearer secret",
        "cookie": "session=secret",
        "x-csrf-token": "secret",
        "content-type": "application/json",
    }
    redacted = redact_headers(headers)
    assert redacted["authorization"] == "<redacted>"
    assert redacted["cookie"] == "<redacted>"
    assert redacted["x-csrf-token"] == "<redacted>"
    assert redacted["content-type"] == "application/json"


def test_polldapi_award_json_scores_highly():
    body = {
        "status": "COMPLETE",
        "data": {
            "airBoundGroups": [
                {
                    "airBounds": [
                        {
                            "availabilityDetails": [{"quota": 2}],
                            "prices": {"milesConversion": {"convertedMiles": {"base": 75000}}},
                        }
                    ]
                }
            ]
        },
    }
    score, reasons = score_candidate(
        "https://example.aircanada.com/polldapi?id=abc",
        "xhr",
        body,
    )
    assert score >= 20
    assert any("polldapi" in reason for reason in reasons)
    assert any("airBoundGroups" in reason for reason in reasons)


def test_replay_headers_keep_auth_but_drop_bot_headers():
    headers = {
        "accept": "application/json",
        "authorization": "Bearer session-token",
        "x-csrf-token": "csrf",
        "x-kpsdk-ct": "bot-token",
        "sec-fetch-site": "same-origin",
    }
    replay = _replay_headers(headers)
    assert replay["accept"] == "application/json"
    assert replay["authorization"] == "Bearer session-token"
    assert replay["x-csrf-token"] == "csrf"
    assert "x-kpsdk-ct" not in replay
    assert "sec-fetch-site" not in replay


def test_session_cookie_filter_excludes_bot_cookies():
    cookies = [
        {"name": "session", "value": "abc"},
        {"name": "bm_sz", "value": "bot"},
        {"name": "_abck", "value": "bot2"},
    ]
    filtered = _safe_session_cookies(cookies)
    assert filtered == {"session": "abc"}
