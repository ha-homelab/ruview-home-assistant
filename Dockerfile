# SPDX-License-Identifier: MIT
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY LICENSES ./LICENSES
COPY src ./src
RUN python3 -m pip install --no-cache-dir . \
    && useradd --uid 10001 --create-home app
USER 10001:10001
ENTRYPOINT ["ruview-home-assistant"]
