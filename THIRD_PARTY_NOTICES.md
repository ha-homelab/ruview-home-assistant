# Third-party notices

The MIT license in `LICENSE` applies to project-owned bridge code, documentation and synthetic fixtures. It does not relicense installed dependencies, Python, base-container contents, external collectors, firmware or Home Assistant. No third-party collector/firmware/model code is vendored in this repository.

Runtime dependencies are installed separately:

- **Eclipse Paho MQTT Python 2.1.0** — `EPL-2.0 OR BSD-3-Clause`, as declared by its distribution. [Upstream](https://github.com/eclipse-paho/paho.mqtt.python). Preserve the bundled [license text](LICENSES/paho-mqtt.txt) when redistributing it.
- **websockets 17.2** — `BSD-3-Clause`. [Upstream](https://github.com/python-websockets/websockets). Preserve the bundled [license text](LICENSES/websockets.txt) when redistributing it.

The notice texts were taken from the exact installed dependency distributions. Python's standard library and the `python` Docker image carry their own licenses. Build/development dependencies (setuptools, build, packaging, pyproject-hooks and Ruff) also retain their upstream licenses and are not bundled as project source.

RuView and Home Assistant names describe interoperability. This project is not an official Home Assistant integration or an endorsement by those projects. Evaluate and comply with the licenses of the particular collector, firmware and optional module producer that you deploy independently.

## Shared release tooling

Generated release and workflow-contract helpers are from [venus-os-ci-toolkit](https://github.com/victron-venus/venus-os-ci-toolkit), pinned by `.release-policy.json`. The following license applies to those files.

MIT License

Copyright (c) 2026 victron-venus

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
