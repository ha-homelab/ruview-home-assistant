# Contributing

Use Python 3.11 or newer and create a virtual environment. Install `.[dev]`, then run `./scripts/check.sh`. Tests must remain offline and synthetic. Do not access a contributor's collector, MQTT broker or Home Assistant instance from tests.

Keep pull requests focused. Add regression coverage for changes to age arithmetic, fail-closed behavior, placement gates, identity/provenance, HTTP bounds and MQTT contracts. Document compatibility changes and update `CHANGELOG.md`. Keep `version`, `pyproject.toml` and `__version__` synchronized.

Do not contribute live payload dumps, credentials, private hostnames, device inventories, room layouts or runtime evidence. Build the smallest invented fixture that demonstrates a problem. Code and examples contributed to this repository are offered under its MIT license; preserve any applicable third-party notices and do not copy third-party code without compatible licensing and attribution.

The generic bridge is intentionally separate from deployment inventories and analytical engines. Improvements should be configurable, testable offline and honest about experimental recognition behavior.


## Project participation

Use public GitHub issues and pull requests for questions, proposals and reproducible non-sensitive bugs. English is the shared discussion language. Read [governance](GOVERNANCE.md), [Code of Conduct](CODE_OF_CONDUCT.md) and the [roadmap](ROADMAP.md). All major functionality changes require automated regression coverage, including relevant negative cases, and updated interface documentation. Resolve review findings and required CI failures before normal merge. Original contributions are accepted under the repository MIT license; preserve third-party licensing and attribution.
