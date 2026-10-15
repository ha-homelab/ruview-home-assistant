# Troubleshooting

## No entities appear

Run `ruview-replay` first to confirm the installed package works. Then check your own broker connection and Home Assistant MQTT integration. Verify both use the same discovery prefix. A node is discovered when the collector lists it or you explicitly list its ID in `RUVIEW_NODE_IDS`. MQTT client IDs must be unique. Logs intentionally show error classes rather than URLs, headers, credentials or live payloads.

## Presence or motion is unavailable, but diagnostics work

Check the node's placement availability. Missing placement and `valid: false` deliberately gate occupancy-related entities. Confirm the physical node mapping before setting placement valid. `room_coverage_validation: unverified` is expected and is not an error.

## Every node is unavailable

Check the collector source identifiers, timestamp units and clocks, active CSI status, per-node classifications and age fields against the v1 contract. `active` is a supported moving classification. Simulated source markers, missing per-node inference, duplicate IDs, future timestamps and ages above 10 seconds fail closed. A working aggregate classification does not satisfy per-node validation.

## Optional modules never become available

Confirm the separate producer implements `/v1/latest` and `ruview.server-modules.v1`. Check clock alignment, exact provenance, explicit experimental status and the 2-second lease. A healthy primary observation older than 2 seconds is still too old for module diagnostics. HTTP/gzip bodies exceeding 1 MiB, concatenated gzip members and mismatched hashes are rejected. The adapter does not start or install a producer for you.

## Optional possible-fall entity is unavailable

Set an explicit compatible `RUVIEW_WS_URL` if you intend to evaluate edge flags. The stream must send boolean `fall_detected` and a valid integer node identity. Current collector observations and confirmed placement are also required. Disconnecting the stream clears cached edge flags. A displayed flag remains an unverified heuristic.

## TLS or authentication fails

Use a hostname present in the broker certificate. Mount the appropriate CA/client files inside the container and check file readability by UID 10001. Provide both client certificate and private key when using mutual TLS. Do not disable certificate verification to bypass an error. For secret files, use exactly one of the direct variable or corresponding `_FILE` variable.

## Old entities remain after changing namespaces

Home Assistant discovery is retained by the broker. Stop the obsolete bridge and deliberately remove only its old discovery configuration records through your broker tools. The package avoids automatic wildcard deletion. Prefer stable identity prefixes to prevent duplicates.

When reporting a bug, include the package/Python versions, a minimal invented JSON fixture, expected behavior and error class. Omit raw private payloads, tokens, IP addresses, device inventories and room layouts.
