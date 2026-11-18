# Documentation

A bridge that republishes RuView collector data into Home Assistant over MQTT,
with its payload contract, deployment notes and release path.

## Understand it

- [Scope and limitations](beta.md) — what the bridge and its diagnostic adapters do, and what they do not.
- [Payload contract v1](payload-contract-v1.md) — the accepted collector shape and the MQTT messages emitted.
- [Configuration](configuration.md) — the environment variables and config fields, and what is absent.
- [Python API and migration](python-api.md) — the distribution and import package names and how to import it.

## Run it

- [Deployment, upgrades and recovery](operations.md) — what the release channel describes and how to recover.
- [Strict transport profile](strict-tls.md) — the variables that switch on strict TLS.
- [Troubleshooting](troubleshooting.md) — starting with `ruview-replay` before the broker and Home Assistant.
- [Quality and security evidence](quality.md) — what the Quality gate actually runs.

## Release operation

- [CI and release operations](release-workflow.md) — `.release-policy.json` and the required status.
- [Version plans and manifest synchronization](VERSIONING.md) — the versioning opt-in.
- [Qualified GitHub CLI for release operations](release-github-cli.md) — the pinned CLI and Go versions.
- [Patched release signer and verifier](release-signer.md) — why the signer binary is exported only after its contract job.
- [Verify a signed release](release-signatures.md) — checking a signed artefact.
- [Verified release-client transport profile](release-tls-profile.md) — the two separately qualified clients.
- [Release-candidate fuzz testing](fuzzing.md) — the target that mutates synthetic server-module snapshots.
- [Fuzzing release candidates](rc-fuzzing.md) — the reusable bounded fuzz workflow.
- [Release read recovery and rerun validation](release-read-safety.md) — the two fixes carried from the shared toolkit.
- [Early final-build runner check](runner-preflight.md) — why the check runs before the final build.
