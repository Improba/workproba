from app.schemas import ErrorEvent, make_error_event


def test_error_event_accepts_optional_correlation_fields() -> None:
    event = ErrorEvent(
        code="agent_error",
        message="boom",
        turn_id="turn_1",
        work_id="work_1",
        session_id="sess_1",
        incident_id="inc_1",
    )
    payload = event.model_dump()
    assert payload["turn_id"] == "turn_1"
    assert payload["work_id"] == "work_1"
    assert payload["session_id"] == "sess_1"
    assert payload["incident_id"] == "inc_1"


def test_make_error_event_generates_incident_id() -> None:
    event = make_error_event(
        code="internal_error",
        message="oops",
        turn_id="turn_2",
        work_id="work_2",
        session_id="sess_2",
    )
    assert event.incident_id
    assert len(event.incident_id) >= 8
