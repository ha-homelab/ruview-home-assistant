# SPDX-License-Identifier: MIT
"""Bounded, explicitly experimental server-module diagnostics for HA.

These outputs never supply presence, fall, posture, count or person coordinates.
Receipt of a cached HTTP/MQTT response cannot renew an event's observation time.
"""

import math
import re

MAX_AGE_MS = 5000
PRODUCER_MAX_AGE_MS = 2000
MAX_EVENTS = 64
MAX_RESPONSE_BYTES = 1024 * 1024
STATES = {"running", "warming_up", "ineligible", "unavailable", "faulted", "stale"}


def text(value, maximum=128):
    if not isinstance(value, str) or not 0 < len(value) <= maximum:
        raise ValueError("Invalid bounded text")
    if any(ord(c) < 32 for c in value):
        raise ValueError("Control character")
    return value


def integer(value, maximum=2**64 - 1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid unsigned integer")
    return value


def decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,19}", value):
        raise ValueError("Invalid decimal integer string")
    integer(int(value))
    return value


def number(value, lower=0, upper=1e15):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not lower <= value <= upper
    ):
        raise ValueError("Invalid finite number")
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("Invalid digest")
    return value


def age(value, observed_ns, generated_ns):
    # Permit at most 250 ms of wall-clock skew, never a future observation
    # relative to the same producer's snapshot.
    observed = int(decimal(observed_ns))
    if observed > generated_ns:
        raise ValueError("Observation after snapshot")
    return max(number(value), (generated_ns - observed) / 1_000_000)


def decode(snapshot, received_wall_ns):
    """Validate once on receipt and retain only the documented bounded fields."""
    if snapshot.get("schema") != "ruview.server-modules.v1":
        raise ValueError("Unknown worker schema")
    if snapshot.get("recognition_validated") is not False:
        raise ValueError("Unqualified recognition assertion")
    if snapshot.get("freshness_limit_ms") != PRODUCER_MAX_AGE_MS:
        raise ValueError("Unknown producer freshness contract")
    generated = int(decimal(snapshot["generated_at_ns"]))
    skew_ms = (received_wall_ns - generated) / 1_000_000
    if not -250 <= skew_ms <= MAX_AGE_MS:
        raise ValueError("Stale worker snapshot or clock mismatch")
    transit = max(0, skew_ms)
    common = {
        "schema": "ruview.ha.server-modules.v1",
        "worker_run_id": text(snapshot["worker_run_id"]),
        "clock_id": text(snapshot["clock_id"]),
        "configuration_sha256": digest(snapshot["configuration_sha256"]),
        "snapshot_generated_at_ns": str(generated),
        "source": "esp32",
        "execution": "server",
        "recognition_validated": False,
        "validation": "unverified_algorithm_outputs",
        "event_limit": MAX_EVENTS,
        "producer_freshness_limit_ms": PRODUCER_MAX_AGE_MS,
    }
    nodes = snapshot["nodes"]
    events = snapshot["events"]
    if not isinstance(nodes, list) or len(nodes) > 16:
        raise ValueError("Too many nodes")
    if not isinstance(events, list) or len(events) > 4096:
        raise ValueError("Too many events")
    result = {}
    node_ids = set()
    identities = {}
    for node in nodes:
        if type(node.get("fresh")) is not bool:
            raise ValueError("Missing node freshness")
        node_id = integer(node["node_id"], 255)
        if not node_id or node_id in node_ids:
            raise ValueError("Duplicate/zero node identity")
        node_ids.add(node_id)
        if all(
            node.get(key) is None
            for key in ("sequence", "last_received_at_ns", "age_ms")
        ):
            if node["fresh"] is not False:
                raise ValueError("Unobserved node declared fresh")
            continue
        algorithms = node["algorithms"]
        if not isinstance(algorithms, list) or not 1 <= len(algorithms) <= 64:
            raise ValueError("Invalid algorithm catalog size")
        outputs = []
        identities[node_id] = {}
        for algorithm in algorithms:
            name = text(algorithm["algorithm"], 64)
            version = text(algorithm["algorithm_version"], 64)
            source_hash = digest(algorithm["source_sha256"])
            if name in identities[node_id] or algorithm["availability"] not in STATES:
                raise ValueError("Duplicate algorithm or invalid availability")
            identities[node_id][name] = (version, source_hash)
            outputs.append(
                {
                    "algorithm": name,
                    "algorithm_version": version,
                    "source_sha256": source_hash,
                    "availability": algorithm["availability"],
                    "reason": text(algorithm["reason"], 512),
                    "processed_frames": integer(algorithm["processed_frames"]),
                    "emitted_events": integer(algorithm["emitted_events"]),
                    "max_execution_us": number(algorithm["max_execution_us"]),
                }
            )
        result[node_id] = {
            **common,
            "node_id": node_id,
            "node_epoch": integer(node["node_epoch"]),
            "sequence": integer(node["sequence"], 2**32 - 1),
            "last_received_at_ns": decimal(node["last_received_at_ns"]),
            "worker_csi_age_ms": age(
                node["age_ms"], node["last_received_at_ns"], generated
            )
            + transit,
            "snapshot_age_ms": transit,
            "worker_fresh": node["fresh"],
            "producer_omitted_events": integer(node.get("omitted_events", 0)),
            "algorithms": outputs,
            "events": [],
        }
    seen = set()
    for event in events:
        node_id = integer(event["node_id"], 255)
        if node_id not in result:
            raise ValueError("Event without node")
        node = result[node_id]
        algorithm = text(event["algorithm"], 64)
        if (
            event["worker_run_id"] != node["worker_run_id"]
            or type(event["node_epoch"]) is not int
            or event["node_epoch"] != node["node_epoch"]
            or identities[node_id].get(algorithm)
            != (event["algorithm_version"], event["source_sha256"])
            or event.get("source") != "esp32"
            or event.get("execution") != "server"
            or event.get("classification") != "experimental"
            or event.get("recognition_validated") is not False
        ):
            raise ValueError("Event provenance mismatch")
        occurrence = decimal(event["occurrence_seq"])
        if type(event.get("fresh")) is not bool:
            raise ValueError("Missing event freshness")
        identity = (node_id, occurrence)
        if identity in seen:
            raise ValueError("Duplicate occurrence")
        seen.add(identity)
        node["events"].append(
            {
                "worker_run_id": node["worker_run_id"],
                "node_id": node_id,
                "node_epoch": node["node_epoch"],
                "occurrence_seq": occurrence,
                "algorithm": algorithm,
                "algorithm_version": event["algorithm_version"],
                "source_sha256": event["source_sha256"],
                "event_id": decimal(event["event_id"]),
                "event_name": text(event["event_name"], 128),
                "meaning": text(event["meaning"], 512),
                "value_type": text(event["value_type"], 64),
                "units": text(event["units"], 64),
                "value": number(event["value"], -1e15, 1e15),
                "observed_at_ns": decimal(event["observed_at_ns"]),
                "observed_monotonic_ns": decimal(event["observed_monotonic_ns"]),
                "source_sequence": integer(event["source_sequence"], 2**32 - 1),
                "age_ms": age(event["age_ms"], event["observed_at_ns"], generated)
                + transit,
                "producer_fresh": event["fresh"],
                "classification": "experimental",
                "recognition_validated": False,
                "source": "esp32",
                "execution": "server",
            }
        )
    for node in result.values():
        node["events"].sort(key=lambda item: int(item["occurrence_seq"]), reverse=True)
        node["omitted_events"] = node["producer_omitted_events"] + max(
            0, len(node["events"]) - MAX_EVENTS
        )
        del node["events"][MAX_EVENTS:]
    return result


def current(decoded, elapsed_ms, core_observations):
    """Apply monotonic cache age and current independent collector freshness."""
    number(elapsed_ms)
    result = {}
    for node_id, stored in decoded.items():
        core = core_observations.get(node_id)
        if core is None or stored["worker_fresh"] is not True:
            continue
        snapshot_age = stored["snapshot_age_ms"] + elapsed_ms
        csi_age = stored["worker_csi_age_ms"] + elapsed_ms
        if (
            max(
                snapshot_age,
                csi_age,
                number(core["csi_age_ms"]),
                number(core["inference_age_ms"]),
            )
            > PRODUCER_MAX_AGE_MS
        ):
            continue
        algorithms = [dict(item) for item in stored["algorithms"]]
        status = {item["algorithm"]: item["availability"] for item in algorithms}
        events = []
        for event in stored["events"]:
            event_age = event["age_ms"] + elapsed_ms
            events.append(
                {
                    **event,
                    "age_ms": round(event_age, 3),
                    "fresh": event["producer_fresh"]
                    and event_age <= PRODUCER_MAX_AGE_MS
                    and status[event["algorithm"]] == "running",
                }
            )
        running = sum(item["availability"] == "running" for item in algorithms)
        result[node_id] = {
            **stored,
            "state": "experimental" if running else "waiting_for_eligible_input",
            "snapshot_age_ms": round(snapshot_age, 3),
            "worker_csi_age_ms": round(csi_age, 3),
            "csi_age_ms": core["csi_age_ms"],
            "inference_age_ms": core["inference_age_ms"],
            "running_algorithms": running,
            "fresh_event_count": sum(item["fresh"] for item in events),
            "freshness_limit_ms": PRODUCER_MAX_AGE_MS,
            "algorithms": algorithms,
            "events": events,
        }
    return result
