# SPDX-License-Identifier: MIT
"""Explicit, instance-local settings. Importing the package never reads secrets."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


def _url(value, schemes, name, optional=False):
    if optional and not value:
        return
    parsed = urlsplit(value)
    if (
        parsed.scheme not in schemes
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{name} must be an absolute URL without credentials/query/fragment"
        )
    try:
        _ = parsed.port
    except ValueError:
        raise ValueError(f"Invalid port in {name}") from None


def _secret(env, key):
    filename = env.get(key + "_FILE")
    if filename and env.get(key):
        raise ValueError(f"Set only {key} or {key}_FILE")
    return Path(filename).read_text().rstrip("\r\n") if filename else env.get(key, "")


def _boolean(env, key, default=False):
    value = env.get(key)
    if value is None:
        return default
    if value.lower() not in {"true", "false", "1", "0"}:
        raise ValueError(f"{key} must be true/false or 1/0")
    return value.lower() in {"true", "1"}


@dataclass(frozen=True)
class Config:
    """Configuration for one bridge; safe to construct independently of os.environ."""

    upstream_url: str = "http://127.0.0.1:3000"
    api_token: str = field(default="", repr=False)
    websocket_url: str = ""
    modules_url: str = ""
    node_ids: tuple[int, ...] = ()
    node_placements_json: str = "{}"
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_client_id: str = "ruview-home-bridge"
    mqtt_username: str = field(default="", repr=False)
    mqtt_password: str = field(default="", repr=False)
    strict_tls: bool = False
    mqtt_tls: bool = False
    mqtt_ca_certs: str | None = None
    mqtt_certfile: str | None = None
    mqtt_keyfile: str | None = field(default=None, repr=False)
    topic_prefix: str = "ruview/home"
    discovery_prefix: str = "homeassistant"
    identifier_prefix: str = "ruview_home"

    def __post_init__(self):
        _url(self.upstream_url, {"http", "https"}, "RUVIEW_URL")
        _url(self.modules_url, {"http", "https"}, "RUVIEW_MODULES_URL", optional=True)
        _url(self.websocket_url, {"ws", "wss"}, "RUVIEW_WS_URL", optional=True)
        if type(self.strict_tls) is not bool:
            raise ValueError("strict_tls must be a boolean")
        if self.strict_tls and (
            urlsplit(self.upstream_url).scheme != "https"
            or (self.modules_url and urlsplit(self.modules_url).scheme != "https")
            or (self.websocket_url and urlsplit(self.websocket_url).scheme != "wss")
            or not self.mqtt_tls
        ):
            raise ValueError("Strict TLS requires HTTPS/WSS endpoints and MQTT_TLS")
        if any(type(n) is not int or not 1 <= n <= 255 for n in self.node_ids):
            raise ValueError("Configured firmware node IDs must be in 1..255")
        if type(self.mqtt_port) is not int or not 1 <= self.mqtt_port <= 65535:
            raise ValueError("MQTT port must be in 1..65535")
        for name, value in (
            ("topic prefix", self.topic_prefix),
            ("discovery prefix", self.discovery_prefix),
        ):
            if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", value):
                raise ValueError(f"Invalid MQTT {name}")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.identifier_prefix):
            raise ValueError(
                "Identifier prefix must contain letters, digits, '_' or '-'"
            )
        if not self.mqtt_client_id or any(ord(c) < 32 for c in self.mqtt_client_id):
            raise ValueError("Invalid MQTT client ID")
        if not self.mqtt_host or any(c.isspace() for c in self.mqtt_host):
            raise ValueError("Invalid MQTT hostname")
        if bool(self.mqtt_certfile) != bool(self.mqtt_keyfile):
            raise ValueError(
                "MQTT client certificate and key must be supplied together"
            )
        if (self.mqtt_ca_certs or self.mqtt_certfile) and not self.mqtt_tls:
            raise ValueError("MQTT_TLS must be enabled when TLS files are supplied")
        if self.mqtt_password and not self.mqtt_username:
            raise ValueError("MQTT password requires a username")

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        tls = _boolean(env, "MQTT_TLS")
        return cls(
            upstream_url=env.get("RUVIEW_URL", "http://127.0.0.1:3000").rstrip("/"),
            api_token=_secret(env, "RUVIEW_API_TOKEN"),
            websocket_url=env.get("RUVIEW_WS_URL", ""),
            modules_url=env.get("RUVIEW_MODULES_URL", "").rstrip("/"),
            node_ids=tuple(
                int(n.strip())
                for n in env.get("RUVIEW_NODE_IDS", "").split(",")
                if n.strip()
            ),
            node_placements_json=env.get("RUVIEW_NODE_PLACEMENTS", "{}"),
            mqtt_host=env.get("RUVIEW_MQTT_HOST", "127.0.0.1"),
            mqtt_port=int(env.get("MQTT_PORT", "8883" if tls else "1883")),
            mqtt_client_id=env.get("MQTT_CLIENT_ID", "ruview-home-bridge"),
            mqtt_username=env.get("MQTT_USERNAME", ""),
            mqtt_password=_secret(env, "MQTT_PASSWORD"),
            mqtt_tls=tls,
            strict_tls=_boolean(env, "RUVIEW_STRICT_TLS"),
            mqtt_ca_certs=env.get("MQTT_CA_CERTS") or None,
            mqtt_certfile=env.get("MQTT_CERTFILE") or None,
            mqtt_keyfile=env.get("MQTT_KEYFILE") or None,
            topic_prefix=env.get("MQTT_TOPIC_PREFIX", "ruview/home"),
            discovery_prefix=env.get("MQTT_DISCOVERY_PREFIX", "homeassistant"),
            identifier_prefix=env.get("MQTT_IDENTIFIER_PREFIX", "ruview_home"),
        )
