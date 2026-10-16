# Security policy

The latest stable release and current 0.1 source line receive security fixes. Report vulnerabilities through [GitHub private reporting](https://github.com/ha-homelab/ruview-home-assistant/security/advisories/new) or **alvit.work@gmail.com**. Never post real credentials, private payloads, hostnames or device inventories in an issue.

Please include the affected version, attack preconditions and a synthetic reproducer. The maintainer aims to acknowledge within 14 days, reproduce and assess the report privately, coordinate disclosure, and test fixes. Critical issues are addressed immediately; other medium-or-higher issues should be fixed within 60 days. Release notes include advisory identifiers and reporter credit unless anonymity is requested. There is no backup maintainer or independent security team.

The bridge handles supplied service URLs and network responses. Use trusted service configuration, verified HTTPS/WSS or MQTT TLS where needed, and restrict broker permissions to the intended discovery/state namespaces and HA status subscription. TLS verification is enabled whenever MQTT TLS is selected. State messages are not retained, while discovery and availability are retained deliberately.

Freshness/placement gates reduce misleading output but are not safety certifications. This project is not an emergency, healthcare or security monitoring system.


The optional [strict transport profile](docs/strict-tls.md) requires encrypted
transports and a stronger verified certificate-chain policy across all owned
HTTP, WebSocket and MQTT clients. Default trusted-local-network operation may
use plaintext and does not provide equivalent confidentiality.
