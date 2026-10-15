# Payload contract v1

The contracts below describe the package's accepted collector shape and emitted MQTT messages. No upstream semantic-version compatibility is assumed. Test your collector against these fields. Unknown upstream diagnostic fields are discarded.

## Collector input

`GET /health` must contain `{"source":"esp32"}`. `GET /api/v1/sensing/latest` must identify the same source and supply a Unix-seconds `timestamp` plus per-node `nodes`. Each node needs integer `node_id`, `node_inference.classification` and finite nonnegative `node_inference.age_ms`. Optional `rssi_dbm` is accepted only from -120 to 0; optional confidence must be finite. A number is never accepted where it is actually a JSON boolean.

`GET /api/v1/nodes` supplies `nodes` with `node_id`, `csi_status: "active"` and finite nonnegative `csi_last_seen_ms`. Duplicate identities and malformed node lists fail closed. The accepted classification values are `absent`, `present_still`, `present_moving` and `active`; `active` normalizes to `present_moving`, while `classification_raw` preserves the source value. Aggregate classification, skeletons, coordinates, counts and biometric estimates do not provide fallback observations.

At evaluation, the latest timestamp, CSI age and inference age must each be at most 10,000 ms old. Request/processing elapsed time accrues onto CSI and inference ages; negative elapsed values are invalid. Future latest timestamps fail closed. Publication delay and transport delay are not proof of fresh data: consumers should use expiration and independent timestamps appropriate to their use case.

## MQTT output

For the default prefix, node `N` uses `ruview/home/nodeN`:

- `/state`: unretained JSON with `presence` and `motion` (`ON`/`OFF`), `classification` and `signal` (number or null).
- `/attributes`: unretained JSON including `schema: "ruview.ha.node-attributes.v1"`, node identity, raw classification, confidence, CSI/inference ages, `calibration: "unverified"` and placement fields.
- `/availability`: retained `online` only while a current valid node observation is available; otherwise `offline`.
- `/placement/availability`: retained `online` only for explicit valid placement.
- Global `ruview/home/availability`: retained process/collector availability and MQTT last will.

Home Assistant discovery is retained at `homeassistant/<component>/ruview_home_nodeN/<key>/config`. Entities require all relevant availability topics; presence/motion additionally require placement. Ordinary entities expire after 15 seconds without a state message. Unknown/stale is unavailable, never an inferred `OFF` value.

Discovery is refreshed when nodes appear, after MQTT connection/HA birth messages, and periodically. Normal collector/state cadence is 2 seconds. Enabling modules requests a 0.5-second polling cadence while ordinary state remains at 2 seconds. Missed polling deadlines are skipped rather than replayed in a burst.

## Optional edge flags

An explicit WebSocket endpoint may deliver `{"type":"edge_vitals","node_id":1,"fall_detected":true}`. The ID must be an integer `1..255` and the flag a boolean. Flags are eligible only with fresh independent collector observations and local edge receipt age at most 10 seconds. A true flag has a 10-second hold, but the hold cannot revive an expired edge receipt. Stream disconnects clear cached flags.

`/fall/state` carries only `fall_detected`; `/fall/attributes` includes `schema: "ruview.ha.fall-attributes.v1"`, `validation: "unverified_heuristic"`, edge age, hold and placement fields. `/fall/availability` provides another gate. These are unverified flags, not confirmed falls. Edge receipt freshness cannot establish when a producer originally generated a queued flag.

## Optional server-module diagnostics

The adapter accepts `ruview.server-modules.v1`, requiring `recognition_validated: false` and `freshness_limit_ms: 2000`. Nanosecond timestamps and occurrence/event IDs are decimal strings to avoid JSON precision loss. Identity/provenance must agree across worker run, node epoch, algorithm version and source SHA-256. The supported producer shape is illustrated by `tests/fixtures/modules.synthetic.json`.

At most 16 nodes, 64 algorithms per node and 4096 input events are accepted. Output retains at most 64 events per node with an omitted count. Text and numeric fields are bounded. Receipt permits at most 250 ms future clock skew and rejects snapshots more than 5 seconds old; publication independently requires snapshot, worker CSI, collector CSI and collector inference ages at most 2 seconds. Producer event age and absolute observation time are both honored. Cached re-delivery cannot renew an event. A stale event may remain in diagnostics with `fresh: false`; it is not a new occurrence.

`/modules/observation` is one unretained envelope with `state` and `attributes`. Attributes use `schema: "ruview.ha.server-modules.v1"` and include a pre-serialization `published_at_ns` timestamp. Consumers must accrue subsequent transport delay and deduplicate using worker run, node, epoch and occurrence identity. `/modules/availability` is retained; the HA diagnostic sensor expires after 7 seconds. HA display expiration does not extend a 2-second event lease.

## Evolution

The schemas under `schemas/` describe emitted envelopes and attributes. Additive diagnostic fields may appear in v1; consumers should ignore unknown fields. Incompatible units, identity or freshness semantics require a new contract version. Release notes call out interface changes. Replay input/result use `ruview.replay.v1` and `ruview.replay-result.v1`; neither is live sensing evidence.
