"""Mutate module diagnostics and prove cached observations cannot renew freshness."""

import copy
import json
import sys
from pathlib import Path

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
with atheris.instrument_imports():
    from ruview_home_assistant import module_observations as modules

NOW = 1791244801000000000


def test_one_input(data):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        return
    try:
        decoded = modules.decode(value, NOW)
    except (ValueError, KeyError, TypeError, AttributeError):
        # These are the explicit validation failures caught by Bridge.poll_modules.
        return
    before = copy.deepcopy(decoded)
    core = {node: {"csi_age_ms": 0, "inference_age_ms": 0} for node in decoded}
    current = modules.current(decoded, 0, core)
    assert modules.current(decoded, modules.MAX_AGE_MS + 1, core) == {}
    assert modules.current(decoded, 0, {}) == {}
    assert before == decoded, "reading freshness must not mutate cached observations"
    for node in current.values():
        assert node["recognition_validated"] is False
        assert len(node["events"]) <= modules.MAX_EVENTS
        assert node["source"] == "esp32"
        for event in node["events"]:
            assert event["recognition_validated"] is False
            if event["fresh"]:
                assert event["age_ms"] <= modules.PRODUCER_MAX_AGE_MS
    assert modules.current(decoded, 0, core) == current


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
