# SPDX-License-Identifier: MIT
"""Deterministic, offline exercise of the production observation/publication code."""

import argparse
import html
import json
from dataclasses import dataclass
from pathlib import Path

from .bridge import Bridge, observations
from .config import Config


@dataclass
class Accepted:
    rc: int = 0


class Recorder:
    """In-memory MQTT-shaped sink; deliberately has no networking methods."""

    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, qos, retain):
        self.messages.append(
            {"topic": topic, "payload": payload, "qos": qos, "retain": retain}
        )
        return Accepted()


def synthetic_frames():
    """All numbers and labels are invented; these are contract tests, not evidence."""
    for label, classification, age, placement in (
        ("Fresh movement", "active", 100, True),
        ("Fresh stillness", "present_still", 100, True),
        ("Fresh absence", "absent", 100, True),
        ("Stale data", "active", 11000, True),
        ("Unverified placement", "active", 100, False),
    ):
        yield {
            "schema": "ruview.replay.v1",
            "label": label,
            "now": 1000,
            "health": {"source": "esp32"},
            "latest": {
                "source": "esp32",
                "timestamp": 1000,
                "nodes": [
                    {
                        "node_id": 1,
                        "rssi_dbm": -60,
                        "node_inference": {
                            "age_ms": age,
                            "classification": classification,
                            "confidence": 0.5,
                        },
                    }
                ],
            },
            "fleet": {
                "nodes": [
                    {"node_id": 1, "csi_status": "active", "csi_last_seen_ms": age}
                ]
            },
            "placements": {
                "1": {
                    "valid": placement,
                    "measurement_location": "synthetic bench",
                    "configured_room": "test_zone",
                }
            },
        }


def replay(frame):
    if frame.get("schema") != "ruview.replay.v1":
        raise ValueError("Unsupported replay schema")
    sink = Recorder()
    bridge = Bridge(
        sink,
        Config(node_ids=(1,), node_placements_json=json.dumps(frame["placements"])),
    )
    bridge.last_discovery = float("inf")
    current = observations(
        frame["health"], frame["latest"], frame["fleet"], frame["now"]
    )
    # Processing is instantaneous on the synthetic replay clock. Real bridges
    # retain the monotonic default and account for time spent publishing.
    bridge.update(current, clock=lambda: 0)
    by_topic = {message["topic"]: message["payload"] for message in sink.messages}
    fresh = by_topic["ruview/home/node1/availability"] == "online"
    placed = by_topic["ruview/home/node1/placement/availability"] == "online"
    state = json.loads(by_topic.get("ruview/home/node1/state", "{}"))
    return {
        "schema": "ruview.replay-result.v1",
        "synthetic": True,
        "label": frame["label"],
        "fresh": fresh,
        "placement_valid": placed,
        "occupancy_entity": state["presence"] if fresh and placed else "unavailable",
        "classification": state.get("classification", "unavailable"),
        "publications": sink.messages,
    }


def render_html(results):
    cards = []
    for result in results:
        value = html.escape(result["occupancy_entity"])
        label = html.escape(result["label"])
        classification = html.escape(result["classification"])
        badge = "good" if value != "unavailable" else "muted"
        cards.append(
            f'<article><p class="label">{label}</p><h2 class="{badge}">{value}</h2><p>{classification}</p><div>Fresh: {str(result["fresh"]).lower()}<br>Placement confirmed: {str(result["placement_valid"]).lower()}</div></article>'
        )
    return (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>RuView synthetic replay</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1421;color:#e8edf5;font:18px system-ui,sans-serif;padding:56px 64px;max-width:1400px}.eyebrow{color:#77c8c6;letter-spacing:.15em;font-size:13px;font-weight:700}h1{font-size:50px;letter-spacing:-.04em;margin:12px 0 18px}header p{color:#b3c1d5;line-height:1.6;max-width:870px}.tag{display:inline-block;padding:7px 12px;border:1px solid #76613f;border-radius:6px;color:#f4cf8e;font-size:13px}section{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:30px 0}article{background:#152234;border:1px solid #2a3d54;border-radius:13px;padding:23px;min-height:217px}.label{font-size:16px;font-weight:600;margin:0}.good{color:#8ae1be}.muted{color:#f4cf8e}h2{font-size:30px;margin:21px 0 8px}article p:not(.label),article div{font-size:14px;color:#9fb1c9;line-height:1.6}article div{border-top:1px solid #2a3d54;padding-top:12px}footer{border-top:1px solid #2a3d54;padding-top:22px;color:#9fb1c9;font-size:15px;line-height:1.7}code{color:#c8e6f6}strong{color:#e8edf5}
</style><header><span class="eyebrow">HA-HOMELAB / RUVIEW HOME ASSISTANT</span><h1>Fresh data. Explicit placement.</h1><span class="tag">SYNTHETIC REPLAY</span><p>The bridge publishes per-node experimental observations and keeps occupancy entities unavailable when source data is stale or placement is unverified.</p></header><section>"""
        + "".join(cards)
        + """</section><footer><strong>What this demonstrates:</strong> the production freshness and placement gates, exercised through an in-memory MQTT sink.<br>All labels, node IDs and measurements are invented. This is a replay visualization, not a Home Assistant screenshot or evidence of occupancy accuracy.<br>Reproduce offline: <code>ruview-replay --format html --output replay.html</code></footer></html>"""
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="JSONL frames following ruview.replay.v1; defaults to invented examples",
    )
    parser.add_argument("--format", choices=("json", "html"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    frames = (
        synthetic_frames()
        if args.input is None
        else [
            json.loads(line)
            for line in args.input.read_text().splitlines()
            if line.strip()
        ]
    )
    results = [replay(frame) for frame in frames]
    output = (
        render_html(results)
        if args.format == "html"
        else json.dumps(results, indent=2, allow_nan=False) + "\n"
    )
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
