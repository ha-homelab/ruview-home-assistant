# Security policy

The latest public beta is the supported line. Report vulnerabilities privately through the repository's GitHub **Security → Report a vulnerability** feature when available. If private reporting is unavailable, open an issue requesting a private contact without exploit details or sensitive data. Never post real credentials, private payloads, hostnames or device inventories in an issue.

Please include the affected version, attack preconditions and a synthetic reproducer. We do not promise a response deadline during beta. We will aim to acknowledge reports, investigate and document fixes.

The bridge handles supplied service URLs and network responses. Use trusted service configuration, verified HTTPS/WSS or MQTT TLS where needed, and restrict broker permissions to the intended discovery/state namespaces and HA status subscription. TLS verification is enabled whenever MQTT TLS is selected. State messages are not retained, while discovery and availability are retained deliberately.

Freshness/placement gates reduce misleading output but are not safety certifications. This project is not an emergency, healthcare or security monitoring system.
