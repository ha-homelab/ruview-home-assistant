# SPDX-License-Identifier: MIT
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from ruview_home_assistant import Config
from ruview_home_assistant.bridge import Bridge
from ruview_home_assistant.module_observations import decode
from ruview_home_assistant.replay import Recorder, replay, synthetic_frames

ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def validate(self, name, value):
        schema = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)

    def test_actual_node_publications_match_versioned_schema(self):
        for frame in synthetic_frames():
            result = replay(frame)
            for message in result["publications"]:
                if message["topic"].endswith("/state"):
                    self.validate("node-state-v1", json.loads(message["payload"]))
                elif message["topic"].endswith("/attributes"):
                    self.validate("node-attributes-v1", json.loads(message["payload"]))

    def test_actual_edge_and_module_attributes_match_schema(self):
        sink = Recorder()
        bridge = Bridge(
            sink, Config(node_ids=(2,), modules_url="http://worker.example.invalid")
        )
        bridge.last_discovery = float("inf")
        bridge.edge_falls.ingest(
            {"type": "edge_vitals", "node_id": 2, "fall_detected": True}, 100
        )
        core = {
            2: {
                "presence": "ON",
                "motion": "ON",
                "signal": -60,
                "classification": "present_moving",
                "csi_age_ms": 100,
                "inference_age_ms": 100,
            }
        }
        fixture = json.loads(
            (ROOT / "tests/fixtures/modules.synthetic.json").read_text()
        )
        bridge.module_snapshot = (decode(fixture, int(fixture["generated_at_ns"])), 100)
        with patch("ruview_home_assistant.bridge.time.monotonic", return_value=100):
            bridge.update(core)
            bridge.update_modules(core)
        by_topic = {m["topic"]: m["payload"] for m in sink.messages}
        self.validate(
            "fall-attributes-v1",
            json.loads(by_topic["ruview/home/node2/fall/attributes"]),
        )
        self.validate(
            "module-observation-v1",
            json.loads(by_topic["ruview/home/node2/modules/observation"]),
        )
