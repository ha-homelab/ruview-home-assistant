# Changelog

## Unreleased security maintenance

- Add an opt-in verified strict TLS policy shared by HTTPS, WSS and MQTT;
  reject plaintext endpoints in the strict profile and preserve stronger host policy.
- Update the build backend to setuptools 83.0.0, including the Unicode MANIFEST normalization fix for GHSA-h35f-9h28-mq5c, and document stable/private support.

## [0.1.0] - 2026-10-15

Initial public beta:

- Importable bridge, bounded HTTP/gzip decoder and optional server-module diagnostic adapter.
- Per-node source, age and placement gates; conservative diagnostic semantics.
- Configurable MQTT namespaces, client identity, port, verified TLS and secret files.
- Synthetic offline replay, documented v1 payload contracts, Python and Docker installation.
- Offline tests and source ZIP, sdist and wheel release tooling.

No occupancy-accuracy claim, live installation evidence, private configuration, firmware or anomaly engine is included.

Release candidate hardening:

- Continue polling when MQTT rejects the fallback offline publication during a disconnect or full queue.
- Reject ambiguous placement/JSON fields and WebSocket redirects; safely reject oversized numeric values.
- Document exact-release deployment, rollback, retained discovery cleanup and the distinction between software stability and experimental sensing.

### Upgrade

This is the first public beta series. Install the published Python wheel or build
the documented Docker image, then supply instance-specific upstream and MQTT
settings. Existing private integrations should use the documented compatibility
API and explicit WebSocket URL when edge events are required.

### Security

Configure verified TLS and secret files where supported. HTTP redirects are
rejected to keep observations and bearer credentials at their configured origin.
Freshness and placement gates remain mandatory; these experimental signals are
not validated for safety decisions. No credentials or real installation evidence
are included in the release.
