# Quality and security evidence

The Quality gate runs the offline unit suite, Ruff, repository validation and Python distribution builds. Tests cover HTTP/WebSocket/MQTT wiring, fail-closed observation processing, and real in-memory TLS handshakes. The strict transport profile and its limits are documented in [strict TLS](strict-tls.md).

Failures and substantive review findings must be resolved before merge. Automated results are bounded evidence, not proof that every defect is absent. No full-function coverage percentage, complete secure-design assurance case or independent maintenance continuity is claimed.

The primary maintainer personally confirmed knowledge of secure-design principles and common Python/network vulnerabilities. The maintainer also confirms no bug, enhancement or vulnerability reports outside GitHub in the preceding 12 months. These are human attestations, not test results; public issue history and current security findings must also be checked when refreshing the assessment.

See [governance](../GOVERNANCE.md), [conduct](../CODE_OF_CONDUCT.md), [roadmap](../ROADMAP.md) and [security policy](../SECURITY.md).

## Complete Python warning review, 2026-10-16

A separate review of the clean source archive at
`23c1a20be666a42c6023776b66345f22ed1cbdee` checked all **56 tracked Python files**,
including inherited release helpers, using **Ruff 0.16.5** with isolated
configuration, the complete F diagnostic family and inline suppressions ignored.
Result: **All checks passed; zero diagnostics**. This is a dated source review;
the routine CI lint/format invocation still covers its documented narrower paths.
It does not claim complete style enforcement or maximum diagnostic coverage.

To reproduce, install that Ruff version, check out the exact source above and run:

```sh
git ls-files -z -- '*.py' | xargs -0 python3 -m ruff check --isolated --select F --ignore-noqa --
```

The recorded review used the equivalent explicit tracked-file list with a clean
`git archive` extraction, so ignored, untracked or modified working files could
not affect the result. No test, query or warning suppression was introduced.

## Container installer maintenance, 2026-10-16

The Dockerfile pins the previously selected Python 3.12 slim base by its immutable
multi-platform digest, then replaces its bundled pip 25.0.1 with the official
pip 26.2.1 wheel before resolving or building project dependencies. The bootstrap
accepts only the exact universal wheel hash in
[`container/requirements-installer.txt`](../container/requirements-installer.txt),
uses no dependency resolution or source build, and disables the installer version
check. Subsequent installation runs the new pip and finishes with `pip check`.

Required CI builds the documented image on Linux amd64 and checks its actual pip
version, non-root UID, runtime imports and all five synthetic production replay
cases with networking disabled and a read-only root filesystem. This does not
claim live MQTT/RuView or device acceptance. The source distribution retains the
bootstrap requirements so its Dockerfile remains usable.

This update addresses the old installer; it is not a clean bill of health for the
base image. The dated base review identified other Debian library/utility findings
that require individual applicability or remediation review. Existing setuid
utilities and independently deployed services are not cleared merely because the
application runs as UID 10001. The package installation still uses normal isolated
build-backend resolution and does not establish a complete locked OS/build graph.
