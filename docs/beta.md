# Scope and limitations

This release packages a generic bridge and bounded diagnostic adapters. It has synthetic tests for source/freshness validation, request-time accounting, MQTT discovery/publication, placement gates, edge-cache behavior, module provenance and leases, gzip bounds, TLS configuration and offline replay. Passing these tests establishes software behavior on these fixtures. It does not establish sensing accuracy, hardware support, end-to-end delivery latency or reliability in a particular home.

The release includes no live measurements, node placement inventory, runtime evidence, collector firmware or model weights. The separate server-module producer and any anomaly engine are out of scope. Dependency notices distinguish our code from third-party packages and externally deployed software.

Start evaluation in a noncritical setup. Compare experimental observations with independently recorded ground truth and record false positives, false negatives, latency and unavailable periods. Keep any identifiable evaluation data private. Test disconnects, old payloads and clock skew before relying on availability gates in a convenience automation. Use a separate MQTT namespace while evaluating alongside an existing bridge.

Useful feedback includes collector field compatibility, a minimal synthetic regression fixture, reproducible packaging issues, and descriptions of unexpected availability transitions. Do not interpret an `ON` state, confidence value, edge flag or module metric as validated recognition. No accuracy percentage is claimed.
