# Configuration

All settings are environment variables, or fields on `ruview_home_assistant.Config`. There are no device, home, network or placement inventories bundled with the project.

## Collector

`RUVIEW_URL` is the collector base HTTP(S) URL, default `http://127.0.0.1:3000`. The bridge reads `/health`, `/api/v1/nodes` and `/api/v1/sensing/latest`. A path prefix is allowed. HTTP proxies from the environment are ignored. Responses must be JSON objects; identity and single-member gzip bodies are limited to 1 MiB both on the wire and after decoding.

`RUVIEW_API_TOKEN` adds a bearer Authorization header to collector HTTP and optional WebSocket requests. Empty means no Authorization header. Alternatively, `RUVIEW_API_TOKEN_FILE` reads the token from a file; do not set both. URLs must not contain credentials, query strings or fragments. Use HTTPS/WSS when collector traffic crosses an untrusted network.

`RUVIEW_WS_URL` is an optional explicit WS(S) endpoint, for example `ws://collector.example.invalid:3001/ws/sensing`. Empty disables edge flags. There is intentionally no inferred WebSocket port. Accepted `edge_vitals` flags remain experimental, and are gated by the independent current node observation.

Use final endpoints: HTTP and WebSocket redirects are rejected. JSON inputs reject duplicate object keys and nonfinite floating-point values. Invalid input makes observations unavailable; it does not become a negative observation.

`RUVIEW_MODULES_URL` optionally points to a separate server-module producer whose `/v1/latest` response follows `ruview.server-modules.v1`. Empty disables this adapter. The producer is not included. Module requests do not send the collector bearer token. Supply this service only on a suitably trusted network or behind an authenticated local proxy. Its failure cannot block collector polling.

## MQTT

- `RUVIEW_MQTT_HOST`: broker host, default `127.0.0.1`.
- `MQTT_PORT`: default `1883`, or `8883` when TLS is enabled.
- `MQTT_CLIENT_ID`: default `ruview-home-bridge`.
- `MQTT_USERNAME` and `MQTT_PASSWORD`: optional credentials. A password requires a username. `MQTT_PASSWORD_FILE` is the file-based alternative to `MQTT_PASSWORD`.
- `MQTT_TLS`: `true`/`false` or `1`/`0`, default `false`.
- `MQTT_CA_CERTS`: optional PEM CA file, otherwise system CAs are used.
- `MQTT_CERTFILE` and `MQTT_KEYFILE`: optional paired PEM client certificate and key files for mutual TLS.
- `MQTT_TOPIC_PREFIX`: state and availability prefix, default `ruview/home`.
- `MQTT_DISCOVERY_PREFIX`: Home Assistant discovery prefix, default `homeassistant`.
- `MQTT_IDENTIFIER_PREFIX`: stable entity/device identity prefix, default `ruview_home`.

TLS always verifies server certificates and hostnames; no insecure mode is provided. TLS file paths are interpreted inside the process/container, so mount files read-only when using Docker. MQTT uses QoS 1. Discovery and availability are retained; observations are not retained. A retained `offline` last will marks unexpected disconnects.

For multiple bridges on one broker, give each a distinct topic prefix, identifier prefix and client ID. The discovery prefix normally stays shared with Home Assistant. Changing identifiers creates new entities; remove obsolete retained discovery records deliberately using your broker's tooling. This bridge does not delete old namespaces.

## Placement

`RUVIEW_NODE_IDS` is an optional comma-separated list of firmware node IDs in `1..255`. Nodes also appear dynamically from the collector. Node IDs are not network addresses.

`RUVIEW_NODE_PLACEMENTS` is a JSON object. The default `{}` confirms nothing. Example with invented labels:

```json
{"1":{"valid":true,"measurement_location":"synthetic bench","configured_room":"test_zone"}}
```

Each entry requires boolean `valid` and nonempty `measurement_location`; `valid: true` also requires a nonempty `configured_room`. Set a real node to valid only after verifying its physical identity and position. Unconfirmed placement leaves presence, motion and possible-fall Home Assistant entities unavailable, while fresh diagnostic classification and signal data remain inspectable. Raw state messages may still exist, so custom MQTT consumers must honor the placement availability topic themselves.

Keys use canonical decimal node IDs (`"1"` through `"255"`). Duplicate keys, leading zeroes, signs, whitespace in keys, and blank location/room names are rejected. See [operations](operations.md) before renaming nodes or removing retained discovery.

`room_coverage_validation` always remains `unverified`. This package does not turn a placement confirmation into an accuracy claim. Location labels are published in MQTT attributes; choose labels appropriate for everyone with access to your broker.
