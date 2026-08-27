import json

import pytest

from llm import extract_json, resolve_base_url, _content_from_response


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_think_tags():
    raw = '<think>reasoning {ignored}</think>\n{"clips": [{"id": 0}]}'
    assert extract_json(raw) == {"clips": [{"id": 0}]}


def test_extract_json_strips_code_fence():
    raw = '```json\n{"ok": true}\n```'
    assert extract_json(raw) == {"ok": True}


def test_extract_json_trailing_data():
    # Object followed by extra junk (e.g. SSE "data: [DONE]" leftovers).
    raw = '{"caption": "hi"}\nsome trailing text'
    assert extract_json(raw) == {"caption": "hi"}


def test_extract_json_repairs_literal_newline_in_string():
    # Models sometimes emit raw newlines inside string values (invalid JSON).
    raw = '{"caption": "line1\nline2", "tags": ["#a"]}'
    parsed = extract_json(raw)
    assert parsed["caption"] == "line1\nline2"
    assert parsed["tags"] == ["#a"]


def test_extract_json_repairs_tab_and_cr():
    raw = '{"v": "a\tb\rc"}'
    assert extract_json(raw) == {"v": "a\tb\rc"}


def test_content_from_response_plain_json():
    body = json.dumps({"choices": [{"message": {"content": "hello"}}]})
    assert _content_from_response(body) == "hello"


def test_content_from_response_sse_stream():
    inner = json.dumps({"choices": [{"message": {"content": "streamed"}}]})
    body = f"data: {inner}\ndata: [DONE]\n\n"
    assert _content_from_response(body) == "streamed"


def test_content_from_response_invalid_raises():
    with pytest.raises(ValueError):
        _content_from_response("not json at all")


def test_resolve_base_url_no_docker(monkeypatch):
    monkeypatch.delenv("IN_DOCKER", raising=False)
    assert resolve_base_url("http://localhost:20128/v1") == "http://localhost:20128/v1"


def test_resolve_base_url_in_docker(monkeypatch):
    monkeypatch.setenv("IN_DOCKER", "1")
    assert resolve_base_url("http://localhost:20128/v1") == "http://host.docker.internal:20128/v1"
    assert resolve_base_url("http://127.0.0.1:20128/v1") == "http://host.docker.internal:20128/v1"


# --- assistant messages that are not a plain string -------------------------
# A reasoning model (nemotron) returned content=null, and the None went straight
# into a regex: "expected string or bytes-like object, got 'NoneType'".

def _envelope(message: dict) -> str:
    import json as _json

    return _json.dumps({"choices": [{"message": message}]})


def test_content_null_falls_back_to_reasoning():
    from llm import _content_from_response

    out = _content_from_response(_envelope({"content": None, "reasoning": '{"a": 1}'}))
    assert out == '{"a": 1}'


def test_content_null_falls_back_to_reasoning_content():
    from llm import _content_from_response

    out = _content_from_response(
        _envelope({"content": None, "reasoning_content": "hello"})
    )
    assert out == "hello"


def test_content_as_a_list_of_parts_is_joined():
    from llm import _content_from_response

    out = _content_from_response(
        _envelope({"content": [{"type": "text", "text": "ab"}, {"type": "text", "text": "cd"}]})
    )
    assert out == "abcd"


def test_plain_string_content_still_wins():
    from llm import _content_from_response

    out = _content_from_response(_envelope({"content": "real", "reasoning": "ignored"}))
    assert out == "real"


def test_empty_message_raises_a_clear_error():
    import pytest as _pytest

    from llm import _content_from_response

    with _pytest.raises(ValueError, match="empty message"):
        _content_from_response(_envelope({"content": None}))


def test_refusal_is_reported():
    import pytest as _pytest

    from llm import _content_from_response

    with _pytest.raises(ValueError, match="refused"):
        _content_from_response(_envelope({"content": None, "refusal": "no"}))


def test_missing_choices_raises_a_clear_error():
    import json as _json

    import pytest as _pytest

    from llm import _content_from_response

    with _pytest.raises(ValueError, match="no choices"):
        _content_from_response(_json.dumps({"choices": []}))


def test_describe_bad_response_shows_a_snippet():
    from clipper import describe_bad_response

    out = describe_bad_response("Let me think about this...\n  the caption should be")
    assert "model replied:" in out
    assert "Let me think about this... the caption should be" in out


def test_describe_bad_response_flags_empty_text():
    from clipper import describe_bad_response

    assert describe_bad_response(None) == " (model returned no text)"
    assert describe_bad_response("   ") == " (model returned no text)"


def test_describe_bad_response_truncates():
    from clipper import describe_bad_response

    out = describe_bad_response("x" * 500)
    assert len(out) < 220
