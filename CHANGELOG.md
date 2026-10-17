# Changelog

## [0.1.1] - 2026-10-17

### Changed

- Add an optional verified strict TLS policy shared by HTTPS, WSS and MQTT clients.
- Update setuptools to 83.0.0, bootstrap the hash-verified pip 26.2.1 wheel in the container and use qualified canonical release clients.
- Apply the Debian XZ security revision, retain the image SBOM and require an actual container build with offline production replay in CI.

### Upgrade

Install the verified Python distribution or rebuild the documented container from this source release. Preserve instance-specific upstream and MQTT settings and the previous image or package for rollback. Enable the strict transport profile only for compatible verified endpoints. Publication does not deploy the bridge.

### Security

Strict mode rejects plaintext endpoints and preserves stronger host policy. Packaging and container changes include the setuptools Unicode MANIFEST normalization fix (GHSA-h35f-9h28-mq5c), reviewed Debian XZ security updates and locked artifact verification. Synthetic replay does not establish occupancy accuracy, device firmware safety or live installation acceptance.

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
