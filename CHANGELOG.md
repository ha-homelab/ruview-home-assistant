# Changelog

## [0.1.3] - 2026-10-20

### Fixed

- Recheck each node's primary and edge-fall freshness after module processing,
  discovery and earlier MQTT publications. Processing time no longer renews
  cached CSI, inference or collector snapshot ages.
- Share the default unverified-placement attributes across primary and module
  publications so both paths retain identical conservative placement semantics.
- Complete the opt-in approval/merge path with the shared metadata-only merger,
  requiring the current review and CI gate before a normal squash merge.

### Upgrade

The `0.1.3-beta` series is for evaluation. Existing MQTT topics, discovery IDs
and positional calls remain compatible. Primary attributes add
`snapshot_age_ms`; cached direct calls to `Bridge.update` can supply their
original monotonic `observed_at` timestamp. Preserve the previous verified
package or image for rollback.

### Security

Regression tests use synthetic clocks and payloads. Freshness accounting before
publication does not prove end-to-end MQTT delivery latency or recognition
accuracy. This release does not validate posture, coordinates or fall detection
and does not deploy or change device firmware.

## [0.1.2] - 2026-10-18

### Changed

- Restore Dependabot approval automation by routing default-branch dependency PR metadata through the trusted target workflow. Trusted-author, draft and opt-in label checks remain enforced; the approval job does not execute PR code.
- Synchronize package version fields for this CI maintenance release.

### Upgrade

Install the verified Python package or rebuild the documented container. Preserve upstream and MQTT settings and the previous package or image for rollback.

### Security

Freshness gates and configured TLS verification remain in force. Synthetic replay does not establish occupancy accuracy, and publication does not deploy the bridge.

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
