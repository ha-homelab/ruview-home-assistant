# Python API and migration

The installable distribution is `ruview-home-assistant`; the import package is `ruview_home_assistant`. Importing modules has no network or credential side effects. The module-observation adapter and HTTP decoder use only the Python standard library.

```python
from ruview_home_assistant import Config
from ruview_home_assistant.bridge import Bridge, observations
from ruview_home_assistant.module_observations import decode, current
from ruview_home_assistant.ruview_http import decode_http_body

config = Config(
    upstream_url="http://collector.example.invalid:3000",
    mqtt_host="broker.example.invalid",
    topic_prefix="evaluation/ruview",
    identifier_prefix="evaluation_ruview",
)
# mqtt_client must implement publish(topic, payload, qos, retain), returning .rc.
# bridge = Bridge(mqtt_client, config)
```

Stable beta entry points retain positional compatibility:

- `observations(health, latest, fleet, now, fleet_elapsed_ms=0, latest_elapsed_ms=0)` returns a per-node mapping; it never performs I/O.
- `node_placements(raw_json)`, `EdgeFalls.ingest(message, now)`, `EdgeFalls.observations(fresh_nodes, now)` and `EdgeFalls.clear()` retain their signatures.
- `discovery(node_id, key)` and `module_discovery(node_id)` additionally accept keyword-only `prefix`, `discovery_prefix` and `identifier_prefix`.
- `Bridge(client, config=None)` reads the environment only if `config` is omitted. Existing `update`, `update_modules`, `update_observations`, `run` and shutdown-event behavior is preserved: request shutdown with `bridge.stopped.set()`.
- `decode(snapshot, received_wall_ns)`, `current(decoded, elapsed_ms, core_observations)` and `decode_http_body(raw, content_encoding, max_bytes)` retain their signatures.

Thin application wrappers can import these functions/classes directly and invoke `bridge.main()` for a command-line process. Avoid wildcard exports and editing package globals: configure each `Bridge` independently. Patch tests at the implementation path, for example `ruview_home_assistant.bridge.time.monotonic`, rather than at a re-exporting wrapper.

## Moving an existing installation

Pin the package to a reviewed version. Keep your service credentials, broker addresses, collector deployment, node/room inventory, automations and any private analytical engines in your own deployment repository. Install the package as a dependency and replace copied generic modules with imports; do not publish private overlays as examples.

The default topic/device identity scheme remains `ruview/home` and `ruview_home`, preserving legacy discovery IDs. Explicitly set `RUVIEW_WS_URL` to retain optional edge-flag behavior: the public package disables WebSockets by default. Explicitly set `RUVIEW_MQTT_HOST`: its public default is loopback. Existing `RUVIEW_URL`, API-token, node-ID, placement and module-URL environment names remain supported. Collector tokens and MQTT authentication are now optional for isolated evaluation deployments.

The HTTP collector reader now also bounds identity/gzip responses to 1 MiB, malformed/duplicate node identities fail closed, and attributes add versioned schema identifiers. Existing downstream consumers must ignore additive attributes. This package does not include a private anomaly engine, collector runtime, firmware, deployments or historical measurements.
