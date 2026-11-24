# SPDX-License-Identifier: MIT
FROM python:3.15-slim@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# The pinned base predates DSA-6549-1. Keep Debian signature verification enabled
# and upgrade only the existing runtime library to the exact security revision.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends --only-upgrade liblzma5=5.8.1-1+deb13u2 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb
# Replace the bundled installer before resolving or building project dependencies.
COPY container/requirements-installer.txt /tmp/requirements-installer.txt
RUN python3 -m pip --isolated --disable-pip-version-check install --no-cache-dir \
    --only-binary=:all: --no-deps --require-hashes -r /tmp/requirements-installer.txt
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY LICENSES ./LICENSES
COPY src ./src
RUN python3 -m pip --isolated --disable-pip-version-check install --no-cache-dir . \
    && python3 -m pip --isolated --disable-pip-version-check check \
    && useradd --uid 10001 --create-home app
USER 10001:10001
ENTRYPOINT ["ruview-home-assistant"]
