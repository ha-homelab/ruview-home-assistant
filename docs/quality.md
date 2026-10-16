# Quality and security evidence

The Quality gate runs the offline unit suite, Ruff, repository validation and Python distribution builds. Tests cover HTTP/WebSocket/MQTT wiring, fail-closed observation processing, and real in-memory TLS handshakes. The strict transport profile and its limits are documented in [strict TLS](strict-tls.md).

Failures and substantive review findings must be resolved before merge. Automated results are bounded evidence, not proof that every defect is absent. No full-function coverage percentage, complete secure-design assurance case or independent maintenance continuity is claimed.

The primary maintainer personally confirmed knowledge of secure-design principles and common Python/network vulnerabilities. The maintainer also confirms no bug, enhancement or vulnerability reports outside GitHub in the preceding 12 months. These are human attestations, not test results; public issue history and current security findings must also be checked when refreshing the assessment.

See [governance](../GOVERNANCE.md), [conduct](../CODE_OF_CONDUCT.md), [roadmap](../ROADMAP.md) and [security policy](../SECURITY.md).
