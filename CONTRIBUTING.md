# Contributing

Use Python 3.11 or newer and create a virtual environment. Install `.[dev]`, then run `./scripts/check.sh`. Tests must remain offline and synthetic. Do not access a contributor's collector, MQTT broker or Home Assistant instance from tests.

Keep pull requests focused. Add regression coverage for changes to age arithmetic, fail-closed behavior, placement gates, identity/provenance, HTTP bounds and MQTT contracts. Document compatibility changes and update `CHANGELOG.md`. Keep `version`, `pyproject.toml` and `__version__` synchronized.

Do not contribute live payload dumps, credentials, private hostnames, device inventories, room layouts or runtime evidence. Build the smallest invented fixture that demonstrates a problem. Code and examples contributed to this repository are offered under its MIT license; preserve any applicable third-party notices and do not copy third-party code without compatible licensing and attribution.

The generic bridge is intentionally separate from deployment inventories and analytical engines. Improvements should be configurable, testable offline and honest about experimental recognition behavior.
