# SPDX-License-Identifier: MIT
import copy
import gzip
import io
import json
import ssl
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import HTTPHandler, build_opener
from urllib.response import addinfourl

from ruview_home_assistant import Config
from ruview_home_assistant.bridge import (
    Bridge,
    configure_mqtt,
    discovery,
    node_placements,
    observations,
)


class ConfigurationTests(unittest.TestCase):
    def test_defaults_are_local_and_optional_streams_disabled(self):
        config = Config.from_env({})
        self.assertEqual(config.mqtt_host, "127.0.0.1")
        self.assertFalse(config.websocket_url)
        self.assertFalse(config.modules_url)
        self.assertEqual(config.node_placements_json, "{}")

    def test_invalid_configuration_fails_before_connection(self):
        for change in (
            {"mqtt_port": 0},
            {"mqtt_port": True},
            {"mqtt_port": 65536},
            {"topic_prefix": "a/#"},
            {"topic_prefix": "a/"},
            {"discovery_prefix": "+"},
            {"identifier_prefix": "a/b"},
            {"upstream_url": "file:///tmp/no"},
            {"upstream_url": "http://user:password@example.invalid"},
            {"upstream_url": "http://example.invalid?token=value"},
            {"websocket_url": "https://example.invalid"},
            {"node_ids": (True,)},
            {"node_ids": (256,)},
            {"mqtt_certfile": "cert.pem"},
            {"mqtt_ca_certs": "ca.pem"},
            {"mqtt_password": "test-only"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                Config(**change)

    def test_legacy_environment_and_new_mqtt_options(self):
        config = Config.from_env(
            {
                "RUVIEW_URL": "https://collector.example.invalid/",
                "RUVIEW_NODE_IDS": "1, 2",
                "RUVIEW_MQTT_HOST": "broker.example.invalid",
                "MQTT_TLS": "true",
                "MQTT_CLIENT_ID": "test-client",
                "MQTT_TOPIC_PREFIX": "test/site",
                "MQTT_IDENTIFIER_PREFIX": "test_site",
            }
        )
        self.assertEqual(config.node_ids, (1, 2))
        self.assertEqual(config.mqtt_port, 8883)
        self.assertEqual(config.upstream_url, "https://collector.example.invalid")
        self.assertEqual(config.topic_prefix, "test/site")

    def test_secrets_from_files_are_not_in_repr(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "token"
            secret.write_text("synthetic-secret\n")
            config = Config.from_env({"RUVIEW_API_TOKEN_FILE": str(secret)})
            self.assertEqual(config.api_token, "synthetic-secret")
            self.assertNotIn("synthetic-secret", repr(config))
            with self.assertRaises(ValueError):
                Config.from_env(
                    {"RUVIEW_API_TOKEN_FILE": str(secret), "RUVIEW_API_TOKEN": "test"}
                )

    def test_tls_always_checks_certificate_and_hostname(self):
        client = Mock()
        configure_mqtt(client, Config(mqtt_tls=True))
        context = client.tls_set_context.call_args.args[0]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        client.tls_insecure_set.assert_not_called()

    def test_custom_namespace_applies_to_every_publication(self):
        client = Mock()
        client.publish.return_value.rc = 0
        config = Config(
            topic_prefix="test/site",
            discovery_prefix="test_discovery",
            identifier_prefix="test_site",
            node_ids=(1,),
        )
        bridge = Bridge(client, config)
        bridge.update({})
        topics = [call.args[0] for call in client.publish.call_args_list]
        self.assertTrue(topics)
        self.assertTrue(
            all(t.startswith(("test/site/", "test_discovery/")) for t in topics)
        )
        self.assertFalse(any("ruview/home" in t for t in topics))
        configs = [
            json.loads(c.args[1])
            for c in client.publish.call_args_list
            if c.args[0].endswith("/config")
        ]
        self.assertTrue(all(c["unique_id"].startswith("test_site_") for c in configs))

    def test_missing_and_invalid_placement_keeps_occupancy_unavailable(self):
        for raw in (
            "{}",
            '{"1":{"valid":false,"measurement_location":"synthetic bench"}}',
        ):
            client = Mock()
            client.publish.return_value.rc = 0
            bridge = Bridge(client, Config(node_ids=(1,), node_placements_json=raw))
            bridge.update({})
            client.publish.assert_any_call(
                "ruview/home/node1/placement/availability",
                "offline",
                qos=1,
                retain=True,
            )
        for raw in (
            "[]",
            '{"1":{"valid":true,"measurement_location":"synthetic bench"}}',
            '{"1":{"valid":"true","measurement_location":"synthetic bench"}}',
        ):
            with self.assertRaises(ValueError):
                node_placements(raw)
        _, payload = discovery(1, "presence")
        self.assertIn(
            {"topic": "ruview/home/node1/placement/availability"},
            payload["availability"],
        )

    def test_primary_http_uses_bounded_gzip_and_optional_auth(self):
        bridge = Bridge(Mock(), Config())
        response = Mock()
        response.read.return_value = gzip.compress(b'{"source":"esp32"}')
        response.headers = {"Content-Encoding": "gzip"}
        bridge.opener = Mock()
        bridge.opener.open.return_value.__enter__ = Mock(return_value=response)
        bridge.opener.open.return_value.__exit__ = Mock(return_value=False)
        self.assertEqual(bridge.get("/health"), {"source": "esp32"})
        request = bridge.opener.open.call_args.args[0]
        self.assertFalse(request.has_header("Authorization"))
        response.read.assert_called_once_with(1024 * 1024 + 1)
        response.read.return_value = b"x" * (1024 * 1024 + 1)
        with self.assertRaises(ValueError):
            bridge.get("/health")

    def test_no_optional_stream_means_no_network_import_or_connection(self):
        bridge = Bridge(Mock(), Config())
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            bridge.listen_falls()
            bridge.listen_modules()

    def test_http_redirects_never_forward_bearer_or_follow_worker_destinations(self):
        received = []

        class MemoryHTTP(HTTPHandler):
            def http_open(self, request):
                received.append((request.selector, request.get_header("Authorization")))
                headers = Message()
                headers["Location"] = "http://other.example.invalid/unexpected"
                response = addinfourl(
                    io.BytesIO(b""),
                    headers,
                    request.full_url,
                    int(request.selector.split("/")[1]),
                )
                response.msg = "Redirect"
                return response

        def memory_opener(*handlers):
            # Exercise urllib's real redirect pipeline without sockets or DNS.
            return build_opener(*handlers, MemoryHTTP())

        base = "http://upstream.example.invalid"
        with patch(
            "ruview_home_assistant.bridge.urllib.request.build_opener", memory_opener
        ):
            bridge = Bridge(
                Mock(), Config(upstream_url=base, api_token="synthetic-only")
            )
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status), self.assertRaises(HTTPError) as error:
                bridge.get(f"/{status}")
            self.assertEqual(error.exception.code, status)
        self.assertEqual(
            received,
            [
                (f"/{status}", "Bearer synthetic-only")
                for status in (301, 302, 303, 307, 308)
            ],
        )

        # The worker uses its independent opener; stop after its first failed poll.
        bridge.module_url = base + "/302"
        bridge.stopped.wait = Mock(side_effect=lambda timeout: bridge.stopped.set())
        with (
            self.assertLogs(level="WARNING"),
            patch(
                "ruview_home_assistant.bridge.urllib.request.build_opener",
                memory_opener,
            ),
        ):
            bridge.listen_modules()
        self.assertEqual(received[-1], ("/302/v1/latest", None))
        self.assertEqual(len(received), 6)

    def test_invalid_ages_and_duplicate_identities_fail_closed(self):
        health = {"source": "esp32"}
        latest = {
            "source": "esp32",
            "timestamp": 1000,
            "nodes": [
                {
                    "node_id": 1,
                    "node_inference": {"classification": "active", "age_ms": 0},
                }
            ],
        }
        fleet = {
            "nodes": [{"node_id": 1, "csi_status": "active", "csi_last_seen_ms": 0}]
        }
        self.assertTrue(observations(health, latest, fleet, 1000))
        for elapsed in (-1, float("nan"), float("inf"), True):
            self.assertEqual(observations(health, latest, fleet, 1000, elapsed), {})
        duplicate = copy.deepcopy(latest)
        duplicate["nodes"] *= 2
        self.assertEqual(observations(health, duplicate, fleet, 1000), {})
        for nodes in (None, [None], [{"node_id": True}], [{"node_id": []}]):
            malformed = {**latest, "nodes": nodes}
            self.assertEqual(observations(health, malformed, fleet, 1000), {})


if __name__ == "__main__":
    unittest.main()
