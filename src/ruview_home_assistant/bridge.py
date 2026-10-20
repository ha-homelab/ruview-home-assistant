# SPDX-License-Identifier: MIT
"""Publish fresh, per-node RuView observations to Home Assistant MQTT discovery.

Occupancy and edge fall flags are experimental until validated. Never publish upstream skeletons,
default node coordinates, aggregate counts, or unvalidated biometric estimates.
"""

import http.client
import json
import logging
import math
import signal
import threading
import time
import urllib.request

from . import module_observations
from .config import Config
from .ruview_http import decode_http_body, strict_json
from .tls import client_context

PREFIX = "ruview/home"
MAX_AGE_MS = 10000
EXPIRE_SECONDS = 15
CLASSIFICATIONS = {"absent": False, "present_still": True, "present_moving": True}
ENTITIES = {
    "presence": ("binary_sensor", "Presence (experimental)", "occupancy"),
    "motion": ("binary_sensor", "Motion (experimental)", "motion"),
    "signal": ("sensor", "Signal strength", "signal_strength"),
    "classification": ("sensor", "Classification (experimental)", None),
}
FALL_ENTITY = ("binary_sensor", "Possible fall (experimental)", "safety")
FALL_HOLD_SECONDS = 10
MODULE_POLL_SECONDS = 0.5
PRIMARY_POLL_SECONDS = 2.0
PLACEMENT_ENTITIES = {"presence", "motion", "fall_detected"}
UNKNOWN_PLACEMENT = {
    "placement_valid": False,
    "measurement_location": "unknown",
    "configured_room": None,
    "room_id": None,
    "room_coverage_validation": "unverified",
}


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Keep both observation requests and bearer credentials at configured URLs."""

    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def node_placements(raw):
    """Fail closed for missing/unverified placement; preserve raw diagnostics."""
    config = strict_json(raw)
    if not isinstance(config, dict):
        raise ValueError("Node placements must be an object")
    result = {}
    for key, value in config.items():
        node_id = int(key)
        if (
            str(node_id) != key
            or not 1 <= node_id <= 255
            or not isinstance(value, dict)
        ):
            raise ValueError("Invalid node placement")
        valid = value.get("valid")
        location = value.get("measurement_location")
        room = value.get("configured_room")
        if (
            type(valid) is not bool
            or not isinstance(location, str)
            or not location.strip()
        ):
            raise ValueError("Placement needs explicit validity and location")
        if valid and (not isinstance(room, str) or not room.strip()):
            raise ValueError("Valid placement needs a configured room")
        if room is not None and (not isinstance(room, str) or not room.strip()):
            raise ValueError("Configured room must be a nonempty string")
        result[node_id] = {
            "placement_valid": valid,
            "measurement_location": location,
            "configured_room": room,
            "room_id": room if valid else None,
            "room_coverage_validation": "unverified",
        }
    return result


class EdgeFalls:
    """Keep per-node live edge flags; a short pulse remains visible for ten seconds."""

    def __init__(self):
        self.lock = threading.Lock()
        self.latest = {}
        self.hold_until = {}

    def clear(self):
        with self.lock:
            self.latest.clear()
            self.hold_until.clear()

    def ingest(self, message, now):
        if not isinstance(message, dict) or message.get("type") != "edge_vitals":
            return
        node_id = message.get("node_id")
        flag = message.get("fall_detected")
        if (
            type(node_id) is not int
            or not 1 <= node_id <= 255
            or type(flag) is not bool
        ):
            return
        with self.lock:
            self.latest[node_id] = (now, flag)
            if flag:
                self.hold_until[node_id] = now + FALL_HOLD_SECONDS

    def observations(self, fresh_nodes, now):
        with self.lock:
            return {
                node_id: {
                    "fall_detected": "ON"
                    if flag or now < self.hold_until.get(node_id, 0)
                    else "OFF",
                    "node_id": node_id,
                    "edge_age_ms": round((now - received) * 1000),
                    "source": "esp32_edge_vitals",
                    "schema": "ruview.ha.fall-attributes.v1",
                    "validation": "unverified_heuristic",
                    "hold_seconds": FALL_HOLD_SECONDS,
                }
                for node_id, (received, flag) in self.latest.items()
                if node_id in fresh_nodes and 0 <= now - received <= MAX_AGE_MS / 1000
            }


def finite_number(value):
    try:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    except OverflowError:
        return False


def fresh_age(value):
    return finite_number(value) and 0 <= value <= MAX_AGE_MS


def observations(health, latest, fleet, now, fleet_elapsed_ms=0, latest_elapsed_ms=0):
    """Require real source, fresh server data, fresh CSI and per-node inference."""
    if not all(isinstance(value, dict) for value in (health, latest, fleet)):
        return {}
    if not all(
        finite_number(value) and value >= 0
        for value in (fleet_elapsed_ms, latest_elapsed_ms)
    ):
        return {}
    if health.get("source") != "esp32" or latest.get("source") != "esp32":
        return {}
    timestamp = latest.get("timestamp")
    if not finite_number(timestamp) or not 0 <= now - timestamp <= MAX_AGE_MS / 1000:
        return {}
    fleet_nodes, latest_nodes = fleet.get("nodes", []), latest.get("nodes", [])
    if not isinstance(fleet_nodes, list) or not isinstance(latest_nodes, list):
        return {}
    if not all(
        isinstance(n, dict) and type(n.get("node_id")) is int
        for n in fleet_nodes + latest_nodes
    ):
        return {}
    statuses = {n["node_id"]: n for n in fleet_nodes}
    if len(statuses) != len(fleet_nodes) or len(
        {n["node_id"] for n in latest_nodes}
    ) != len(latest_nodes):
        return {}
    result = {}
    for node in latest_nodes:
        node_id = node.get("node_id")
        if type(node_id) is not int or not 1 <= node_id <= 255:
            continue
        status = statuses.get(node_id, {})
        inference = node.get("node_inference") or {}
        if not isinstance(inference, dict):
            continue
        classification_raw = inference.get("classification")
        if not isinstance(classification_raw, str):
            continue
        # Pinned collector raw_classify() uses active for its higher-motion state.
        classification = (
            "present_moving" if classification_raw == "active" else classification_raw
        )
        csi_age = status.get("csi_last_seen_ms")
        inference_age = inference.get("age_ms")
        if not fresh_age(csi_age) or not fresh_age(inference_age):
            continue
        csi_age += fleet_elapsed_ms
        inference_age += latest_elapsed_ms
        if (
            status.get("csi_status") != "active"
            or not fresh_age(csi_age)
            or not fresh_age(inference_age)
            or classification not in CLASSIFICATIONS
        ):
            continue
        rssi = node.get("rssi_dbm")
        confidence = inference.get("confidence")
        result[node_id] = {
            "presence": "ON" if CLASSIFICATIONS[classification] else "OFF",
            "motion": "ON" if classification == "present_moving" else "OFF",
            "classification": classification,
            "classification_raw": classification_raw,
            "signal": rssi if finite_number(rssi) and -120 <= rssi <= 0 else None,
            "confidence": confidence if finite_number(confidence) else None,
            "source": "esp32",
            "schema": "ruview.ha.node-attributes.v1",
            "calibration": "unverified",
            "node_id": node_id,
            "csi_age_ms": csi_age,
            "inference_age_ms": inference_age,
            "snapshot_age_ms": (now - timestamp) * 1000,
        }
    return result


def aged_observation(state, elapsed_ms):
    """Advance the original ages without renewing a cached primary observation."""
    if not finite_number(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("Invalid observation age")
    if state is None:
        return None
    ages = {
        key: state.get(key)
        for key in ("csi_age_ms", "inference_age_ms", "snapshot_age_ms")
        if key != "snapshot_age_ms" or key in state
    }
    if not all(fresh_age(value) for value in ages.values()):
        return None
    ages = {key: value + elapsed_ms for key, value in ages.items()}
    return {**state, **ages} if all(map(fresh_age, ages.values())) else None


def discovery(
    node_id,
    key,
    *,
    prefix=PREFIX,
    discovery_prefix="homeassistant",
    identifier_prefix="ruview_home",
):
    component, name, device_class = (
        FALL_ENTITY if key == "fall_detected" else ENTITIES[key]
    )
    base = f"{prefix}/node{node_id}"
    payload = {
        "name": name,
        "unique_id": f"{identifier_prefix}_node{node_id}_{key}",
        "default_entity_id": f"{component}.{identifier_prefix.removesuffix('_home')}_node{node_id}_{key}",
        "state_topic": f"{base}/state",
        "value_template": "{{ value_json." + key + " }}",
        "json_attributes_topic": f"{base}/attributes",
        "expire_after": EXPIRE_SECONDS,
        "availability_mode": "all",
        "availability": [
            {"topic": f"{prefix}/availability"},
            {"topic": f"{base}/availability"},
        ],
        "device": {
            "identifiers": [f"{identifier_prefix}_node{node_id}"],
            "name": f"RuView node {node_id}",
            "manufacturer": "RuView",
            "model": "ESP32 CSI",
        },
    }
    if device_class:
        payload["device_class"] = device_class
    if key == "signal":
        payload.update(unit_of_measurement="dBm", entity_category="diagnostic")
    if key == "classification":
        payload["entity_category"] = "diagnostic"
    if key in PLACEMENT_ENTITIES:
        payload["availability"].append({"topic": f"{base}/placement/availability"})
    if key == "fall_detected":
        payload["state_topic"] = f"{base}/fall/state"
        payload["json_attributes_topic"] = f"{base}/fall/attributes"
        payload["availability"].append({"topic": f"{base}/fall/availability"})
    return (
        f"{discovery_prefix}/{component}/{identifier_prefix}_node{node_id}/{key}/config",
        payload,
    )


def module_discovery(
    node_id,
    *,
    prefix=PREFIX,
    discovery_prefix="homeassistant",
    identifier_prefix="ruview_home",
):
    base = f"{prefix}/node{node_id}/modules"
    return (
        f"{discovery_prefix}/sensor/{identifier_prefix}_node{node_id}/server_modules/config",
        {
            "name": "Server modules (experimental)",
            "unique_id": f"{identifier_prefix}_node{node_id}_server_modules",
            "default_entity_id": f"sensor.{identifier_prefix.removesuffix('_home')}_node{node_id}_server_modules",
            "state_topic": f"{base}/observation",
            "value_template": "{{ value_json.state }}",
            "json_attributes_topic": f"{base}/observation",
            "json_attributes_template": "{{ value_json.attributes | tojson }}",
            "entity_category": "diagnostic",
            "expire_after": 7,
            "availability_mode": "all",
            "availability": [
                {"topic": f"{prefix}/availability"},
                {"topic": f"{base}/availability"},
            ],
            "device": {"identifiers": [f"{identifier_prefix}_node{node_id}"]},
        },
    )


class Bridge:
    # Class defaults also support downstream test doubles constructed with __new__.
    prefix = PREFIX
    discovery_prefix = "homeassistant"
    identifier_prefix = "ruview_home"

    def __init__(self, client, config=None):
        self.config = Config.from_env() if config is None else config
        self.client = client
        self.prefix = self.config.topic_prefix
        self.discovery_prefix = self.config.discovery_prefix
        self.identifier_prefix = self.config.identifier_prefix
        self.known = set(self.config.node_ids)
        self.placements = node_placements(self.config.node_placements_json)
        self.stopped = threading.Event()
        self.rediscover = threading.Event()
        self.last_discovery = 0
        self.last_primary_update = None
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            RejectRedirects(),
            urllib.request.HTTPSHandler(
                context=client_context(strict=self.config.strict_tls)
            ),
        )
        self.base = self.config.upstream_url.rstrip("/")
        self.token = self.config.api_token
        self.edge_falls = EdgeFalls()
        self.fall_thread = threading.Thread(target=self.listen_falls, daemon=True)
        self.module_url = self.config.modules_url.rstrip("/")
        self.module_lock = threading.Lock()
        self.module_snapshot = ({}, 0)
        self.module_thread = threading.Thread(target=self.listen_modules, daemon=True)

    def listen_modules(self):
        """Independent timeout: worker failure cannot delay primary observations."""
        if not self.module_url:
            return
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            RejectRedirects(),
            urllib.request.HTTPSHandler(
                context=client_context(strict=self.config.strict_tls)
            ),
        )
        next_poll = time.monotonic()
        while not self.stopped.is_set():
            try:
                request = urllib.request.Request(
                    self.module_url + "/v1/latest", headers={"Accept-Encoding": "gzip"}
                )
                with opener.open(request, timeout=2) as response:
                    raw = response.read(module_observations.MAX_RESPONSE_BYTES + 1)
                    encoding = response.headers.get("Content-Encoding")
                if len(raw) > module_observations.MAX_RESPONSE_BYTES:
                    raise ValueError("Worker response exceeds bound")
                # Anchor before parsing/decoding so that work cannot renew the cache.
                # Monotonic first makes any delay between clock reads conservative.
                received = time.monotonic()
                received_wall_ns = time.time_ns()
                raw = decode_http_body(
                    raw, encoding, module_observations.MAX_RESPONSE_BYTES
                )
                decoded = module_observations.decode(strict_json(raw), received_wall_ns)
                snapshot = (decoded, received)
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                http.client.HTTPException,
            ) as error:
                logging.warning(
                    "Module diagnostics unavailable (%s)", type(error).__name__
                )
                snapshot = ({}, 0)
            with self.module_lock:
                self.module_snapshot = snapshot
            next_poll = self.wait_for_poll(next_poll, MODULE_POLL_SECONDS)

    def wait_for_poll(self, previous_deadline, period):
        """Keep a monotonic cadence; skip missed ticks instead of catching up."""
        now = time.monotonic()
        next_poll = previous_deadline + period
        if next_poll <= now:
            next_poll += (math.floor((now - next_poll) / period) + 1) * period
        self.stopped.wait(next_poll - now)
        return next_poll

    def update_modules(self, current, core_observed_at=None):
        if not self.module_url:
            return
        with self.module_lock:
            decoded, received = self.module_snapshot
        # All envelopes refer to this one instant, before potentially expensive
        # preparation and serialization. Consumers accrue subsequent delivery time.
        # Wall first prevents a scheduling delay from advancing the lease stamp.
        published_at_ns = time.time_ns()
        sampled_at = time.monotonic()
        core_elapsed_ms = (
            0 if core_observed_at is None else (sampled_at - core_observed_at) * 1000
        )
        if core_elapsed_ms < 0:
            raise ValueError("Core observation anchor is in the future")
        module_core = {
            node_id: {
                **values,
                "csi_age_ms": values["csi_age_ms"] + core_elapsed_ms,
                "inference_age_ms": values["inference_age_ms"] + core_elapsed_ms,
            }
            for node_id, values in current.items()
        }
        diagnostics = module_observations.current(
            decoded, (sampled_at - received) * 1000, module_core
        )
        for node_id in self.known:
            base = f"{self.prefix}/node{node_id}/modules"
            result = diagnostics.get(node_id)
            if result is None:
                self.publish(f"{base}/availability", "offline", retain=True)
                continue
            self.publish(
                f"{base}/observation",
                {
                    "state": result["state"],
                    "attributes": {
                        **{
                            key: value
                            for key, value in result.items()
                            if key != "state"
                        },
                        "published_at_ns": str(published_at_ns),
                        **self.placements.get(node_id, UNKNOWN_PLACEMENT),
                    },
                },
            )
            self.publish(f"{base}/availability", "online", retain=True)

    def listen_falls(self):
        url = self.config.websocket_url
        if not url:
            return
        from websockets.exceptions import InvalidStatus
        from websockets.sync.client import ClientConnection, connect

        class FixedEndpointConnection(ClientConnection):
            def handshake(self, *args, **kwargs):
                try:
                    return super().handshake(*args, **kwargs)
                except InvalidStatus as error:
                    if 300 <= error.response.status_code < 400:
                        raise ValueError(
                            "WebSocket redirects are not allowed"
                        ) from None
                    raise

        while not self.stopped.is_set():
            try:
                with connect(
                    url,
                    ssl=client_context(strict=self.config.strict_tls)
                    if url.startswith("wss:")
                    else None,
                    additional_headers=self.auth_headers(),
                    open_timeout=5,
                    close_timeout=2,
                    max_size=2**20,
                    proxy=None,
                    create_connection=FixedEndpointConnection,
                ) as ws:
                    while not self.stopped.is_set():
                        try:
                            message = ws.recv(timeout=2)
                        except TimeoutError:
                            continue
                        try:
                            self.edge_falls.ingest(
                                strict_json(message), time.monotonic()
                            )
                        except (ValueError, TypeError):
                            continue
            except Exception as error:
                # Error text or request headers can contain credentials; log type only.
                logging.warning("Edge stream unavailable (%s)", type(error).__name__)
            finally:
                self.edge_falls.clear()
            self.stopped.wait(2)

    def auth_headers(self):
        return {"Authorization": "Bearer " + self.token} if self.token else {}

    def get(self, path):
        request = urllib.request.Request(
            self.base + path,
            headers={**self.auth_headers(), "Accept-Encoding": "gzip"},
        )
        with self.opener.open(request, timeout=3) as response:
            raw = response.read(module_observations.MAX_RESPONSE_BYTES + 1)
            encoding = response.headers.get("Content-Encoding")
        decoded = strict_json(
            decode_http_body(raw, encoding, module_observations.MAX_RESPONSE_BYTES)
        )
        if not isinstance(decoded, dict):
            raise ValueError("Expected an upstream JSON object")
        return decoded

    def publish(self, topic, payload, retain=False):
        if isinstance(payload, dict):
            payload = json.dumps(payload, allow_nan=False)
        result = self.client.publish(topic, payload, qos=1, retain=retain)
        if result.rc:
            raise ConnectionError("MQTT publish was not accepted")

    def announce(self):
        for node_id in self.known:
            for key in (*ENTITIES, "fall_detected"):
                topic, payload = discovery(
                    node_id,
                    key,
                    prefix=self.prefix,
                    discovery_prefix=self.discovery_prefix,
                    identifier_prefix=self.identifier_prefix,
                )
                self.publish(topic, payload, retain=True)
            if self.module_url:
                topic, payload = module_discovery(
                    node_id,
                    prefix=self.prefix,
                    discovery_prefix=self.discovery_prefix,
                    identifier_prefix=self.identifier_prefix,
                )
                self.publish(topic, payload, retain=True)
        self.last_discovery = time.monotonic()
        self.rediscover.clear()

    def update(self, current, observed_at=None, *, clock=None):
        clock = time.monotonic if clock is None else clock
        observed_at = clock() if observed_at is None else observed_at
        new = set(current) - self.known
        self.known.update(current)
        if new or self.rediscover.is_set() or clock() - self.last_discovery > 60:
            self.announce()
        self.publish(f"{self.prefix}/availability", "online", retain=True)
        for node_id in self.known:
            base = f"{self.prefix}/node{node_id}"
            placement = self.placements.get(node_id, UNKNOWN_PLACEMENT)
            self.publish(
                f"{base}/placement/availability",
                "online" if placement["placement_valid"] else "offline",
                retain=True,
            )
            # Discovery, module work, and earlier nodes may have consumed the
            # remaining lifetime. Each node keeps the original sample anchor.
            sampled_at = clock()
            state = aged_observation(
                current.get(node_id), (sampled_at - observed_at) * 1000
            )
            falls = self.edge_falls.observations(
                () if state is None else (node_id,), sampled_at
            )
            fall_online = False
            if node_id in falls:
                fall = falls[node_id]
                self.publish(
                    f"{base}/fall/state", {"fall_detected": fall["fall_detected"]}
                )
                self.publish(
                    f"{base}/fall/attributes",
                    {
                        **{k: v for k, v in fall.items() if k != "fall_detected"},
                        **placement,
                    },
                )
                fall_published_at = clock()
                core_fresh = aged_observation(
                    current.get(node_id), (fall_published_at - observed_at) * 1000
                )
                fall_fresh = self.edge_falls.observations(
                    () if core_fresh is None else (node_id,), fall_published_at
                )
                fall_online = node_id in fall_fresh
                self.publish(
                    f"{base}/fall/availability",
                    "online" if fall_online else "offline",
                    retain=True,
                )
            else:
                self.publish(f"{base}/fall/availability", "offline", retain=True)
            # An edge publication can also take time. Recheck before sending
            # primary state, including removing any just-published fall lease.
            state = aged_observation(
                current.get(node_id), (clock() - observed_at) * 1000
            )
            if state is None:
                if fall_online:
                    self.publish(f"{base}/fall/availability", "offline", retain=True)
                self.publish(f"{base}/availability", "offline", retain=True)
                continue
            self.publish(f"{base}/state", {k: state[k] for k in ENTITIES})
            self.publish(
                f"{base}/attributes",
                {**{k: v for k, v in state.items() if k not in ENTITIES}, **placement},
            )
            # Primary payload work may outlive the independent edge lease even
            # while CSI and inference remain fresh.
            if fall_online and node_id not in self.edge_falls.observations(
                (node_id,), clock()
            ):
                self.publish(f"{base}/fall/availability", "offline", retain=True)
                fall_online = False
            state = aged_observation(
                current.get(node_id), (clock() - observed_at) * 1000
            )
            if state is None and fall_online:
                self.publish(f"{base}/fall/availability", "offline", retain=True)
            self.publish(
                f"{base}/availability",
                "online" if state is not None else "offline",
                retain=True,
            )

    def update_observations(self, current, observed_at=None):
        # Publish the short module lease before ordinary discovery/state work.
        # Preserve the original core anchor across preparation and serialization.
        core_observed_at = time.monotonic() if observed_at is None else observed_at
        self.update_modules(current, core_observed_at)
        # Faster module polls must not increase ordinary HA recorder traffic.
        # Sample again so slow module work cannot shorten the primary interval.
        now = time.monotonic()
        if (
            self.last_primary_update is None
            or now - self.last_primary_update >= PRIMARY_POLL_SECONDS
        ):
            self.update(current, observed_at=core_observed_at)
            self.last_primary_update = now

    def run(self):
        next_poll = time.monotonic()
        period = MODULE_POLL_SECONDS if self.module_url else PRIMARY_POLL_SECONDS
        while not self.stopped.is_set():
            if not self.client.is_connected():
                self.stopped.wait(2)
                continue
            try:
                health = self.get("/health")
                fleet_started = time.monotonic()
                fleet = self.get("/api/v1/nodes")
                observed = {
                    node["node_id"]
                    for node in fleet.get("nodes", [])
                    if type(node.get("node_id")) is int and 1 <= node["node_id"] <= 255
                }
                if observed - self.known:
                    self.known.update(observed)
                    self.rediscover.set()
                latest_started = time.monotonic()
                latest = self.get("/api/v1/sensing/latest")
                observed_at = time.monotonic()
                current = observations(
                    health,
                    latest,
                    fleet,
                    time.time(),
                    (observed_at - fleet_started) * 1000,
                    (observed_at - latest_started) * 1000,
                )
                self.update_observations(current, observed_at)
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                http.client.HTTPException,
            ) as error:
                # Never log credentials, request headers, or live payloads.
                logging.warning("Observation unavailable (%s)", type(error).__name__)
                if self.client.is_connected():
                    try:
                        self.publish(
                            f"{self.prefix}/availability", "offline", retain=True
                        )
                    except OSError as publish_error:
                        # A disconnect or full queue can race is_connected().
                        # Keep polling so paho can reconnect and rediscover.
                        logging.warning(
                            "MQTT availability unavailable (%s)",
                            type(publish_error).__name__,
                        )
            # Reserve lease headroom without adding request time to every period.
            next_poll = self.wait_for_poll(next_poll, period)


def configure_mqtt(client, config):
    """Configure authentication, verified TLS and last will before connecting."""
    if config.mqtt_username:
        client.username_pw_set(config.mqtt_username, config.mqtt_password or None)
    if config.mqtt_tls:
        context = client_context(strict=config.strict_tls, cafile=config.mqtt_ca_certs)
        if config.mqtt_certfile:
            context.load_cert_chain(config.mqtt_certfile, config.mqtt_keyfile)
        client.tls_set_context(context)
    client.will_set(
        f"{config.topic_prefix}/availability", "offline", qos=1, retain=True
    )


def main(argv=None):
    import argparse

    from . import __version__

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args(argv)

    import paho.mqtt.client as mqtt

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    config = Config.from_env()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=config.mqtt_client_id
    )
    configure_mqtt(client, config)
    client.max_queued_messages_set(100)
    client.reconnect_delay_set(1, 30)
    bridge = Bridge(client, config)

    def connected(_client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            logging.error("MQTT authentication/connect rejected")
            return
        logging.info("MQTT connected")
        bridge.rediscover.set()
        client.subscribe(f"{config.discovery_prefix}/status", qos=1)

    client.on_connect = connected
    client.on_message = lambda *_: bridge.rediscover.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: bridge.stopped.set())
    client.connect_async(
        config.mqtt_host,
        config.mqtt_port,
        15,
    )
    client.loop_start()
    bridge.fall_thread.start()
    bridge.module_thread.start()
    try:
        bridge.run()
    finally:
        bridge.stopped.set()
        bridge.fall_thread.join(timeout=3)
        bridge.module_thread.join(timeout=3)
        if client.is_connected():
            client.publish(
                f"{config.topic_prefix}/availability", "offline", qos=1, retain=True
            ).wait_for_publish(3)
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
