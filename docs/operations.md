# Deployment, upgrades and recovery

## Choose the software and evaluate the installation separately

The release channel describes the bridge software. A release candidate or stable
package does not validate a collector, firmware, model, placement or sensing
accuracy. Presence, motion and possible-fall outputs remain experimental in every
channel. Availability means the documented source, age and placement gates passed;
it is not proof that a room is occupied or empty.

Use replay to check installation, then evaluate your collector with independently
observed examples. Useful first deployments are signal diagnostics, collector
compatibility checks and controlled comparisons against labels. Establish your own
acceptance criteria before using observations in convenience automations.

## Install one explicitly selected release

Download the wheel and verification files for the intended tag from
[Releases](https://github.com/ha-homelab/ruview-home-assistant/releases). Follow
[release signature verification](release-signatures.md) before installation.
Keep the wheel and its verified source revision for rollback. Install the exact
downloaded wheel in a dedicated Python 3.11 or newer environment:

```sh
python3 -m venv /path/to/ruview-venv
/path/to/ruview-venv/bin/python -m pip install /path/to/downloaded-release.whl
/path/to/ruview-venv/bin/ruview-home-assistant --version
/path/to/ruview-venv/bin/ruview-replay
```

Replace the paths with the actual environment and wheel filename. Python does not
load `.env`; supply settings through your service manager's environment facility.
Keep credentials outside the checkout and readable only by the runtime account.
When using Compose, copy the source for the selected release, configure `.env`,
and build that source. The provided Compose service restarts after failures and
runs with a read-only filesystem. Certificate and secret paths must be mounted
read-only and readable by container UID 10001.

For a Python service, configure your supervisor to restart on failure, use the
environment's absolute executable path and send SIGTERM on shutdown. Allow at
least ten seconds for worker shutdown and the final MQTT availability publish.
Keep service logs; the bridge logs exception classes without payloads or tokens.

## Keep identity stable during an upgrade

Record the topic, discovery and identifier prefixes, MQTT client ID, node IDs and
placement configuration privately. Stop the old instance before starting the
replacement with those settings. Two processes with the same MQTT client ID
disconnect each other; two publishers using the same state topics can mix data.

Test a candidate alongside production only with a separate client ID, topic
prefix and identifier prefix. Use explicit collector and WebSocket URLs. HTTP
and WebSocket redirects are rejected, including redirects on the same host; set
the final endpoint rather than relying on a reverse proxy redirect.

Placement object keys must be canonical decimal IDs, such as `"1"`, without
leading zeroes, signs or whitespace. Duplicate JSON fields are rejected instead
of silently overriding a mapping. Confirm the physical mapping again after
moving, replacing or renumbering a node. Room and location names cannot be blank.

To roll back, stop the replacement and run the saved release in its previous
environment with the saved settings. There is no local bridge database to
migrate. Retained MQTT discovery and availability are separate broker state and
must also be considered if prefixes changed.

## Understand disconnects and stale observations

The bridge requests QoS 1 delivery, but a successful publish call means the local
MQTT client accepted it; it does not confirm Home Assistant consumed it. Paho
reconnects with a bounded backoff. Discovery is republished after broker reconnect,
Home Assistant status messages and periodically during operation. A disconnect
or full queue racing an availability update is logged and polling continues.

Discovery and availability are retained. Observation states are not retained.
Unexpected broker disconnects use the retained `offline` last will. Home Assistant
also applies entity expiry (15 seconds for primary entities, 7 for modules).
Broker detection, network delay and these expiry windows mean unavailable is not
instantaneous. Custom MQTT consumers must implement expiry and all availability
gates themselves, including placement; they must not treat an old `OFF` as a
current empty-room observation.

## Retire a node or namespace deliberately

The bridge remembers nodes discovered during its process lifetime and publishes
them unavailable when they stop reporting. It does not delete discovery records.
Disabling optional modules or moving to a new prefix also leaves old discovery
records on the broker. Stop the old publisher first, then inspect the retained
topics with your broker tooling. For the default node 1 namespace, examples are:

```text
homeassistant/binary_sensor/ruview_home_node1/presence/config
homeassistant/binary_sensor/ruview_home_node1/motion/config
homeassistant/binary_sensor/ruview_home_node1/fall_detected/config
homeassistant/sensor/ruview_home_node1/signal/config
homeassistant/sensor/ruview_home_node1/classification/config
homeassistant/sensor/ruview_home_node1/server_modules/config
```

Remove only reviewed obsolete records using retained zero-length MQTT payloads.
Inspect related retained availability topics under the old state prefix too.
Do not publish wildcard deletions or remove another bridge's namespace. If a
current bridge still knows the node, it will announce that node again; remove it
from the collector/configuration and restart the bridge before retiring it.
