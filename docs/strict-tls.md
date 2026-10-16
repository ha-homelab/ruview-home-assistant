# Strict transport profile

Set `RUVIEW_STRICT_TLS=true`, `MQTT_TLS=true`, `RUVIEW_URL=https://...`, and use
`https://` for an optional `RUVIEW_MODULES_URL` and `wss://` for an optional
`RUVIEW_WS_URL`. Plaintext endpoints are rejected during configuration validation
when this profile is enabled. HTTP and WebSocket redirects remain disabled.

Every owned HTTPS, WSS and MQTT TLS connection uses the same verified context
factory, TLS 1.2 or newer, and OpenSSL 3 security level at least 3. This requires
RSA/DH keys of at least 3072 bits and EC keys of at least 256 bits throughout the
verified certificate chain and rejects static RSA key exchange. A stricter host
policy or narrower cipher selection is preserved. Certificate and hostname
validation remain mandatory; private headers/MQTT authentication are sent only
after the TLS handshake. Incompatible peers fail instead of falling back.

Use a server certificate for the configured hostname. Standard OpenSSL trust
settings apply to HTTPS/WSS; MQTT also accepts the existing `MQTT_CA_CERTS` and
optional client certificate/key settings. Client keys must meet the policy too.
Do not disable verification or substitute a plaintext endpoint to bypass a
failure. This opt-in policy may reject older broker or upstream certificates.

Default local-network operation remains available for compatibility and can use
plaintext HTTP/WS/MQTT; it does not provide transport confidentiality. Configure
broker ACLs and protect credentials independently. This profile does not validate
sensing accuracy, secure third-party firmware, or make untrusted configuration
safe. Test certificates and memory-BIO handshakes are synthetic software evidence,
not a live household deployment.
