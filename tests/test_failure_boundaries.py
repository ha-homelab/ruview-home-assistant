# SPDX-License-Identifier: MIT
import json
import socket
import threading
import unittest
from unittest.mock import Mock, patch

from ruview_home_assistant import module_observations
from ruview_home_assistant.bridge import Bridge, finite_number, node_placements
from ruview_home_assistant.config import Config
from ruview_home_assistant.ruview_http import strict_json


class FailureBoundaryTests(unittest.TestCase):
    def test_rejected_offline_publication_does_not_stop_polling(self):
        bridge = Bridge(Mock(), Config())
        bridge.client.is_connected.return_value = True
        bridge.get = Mock(side_effect=[ValueError("bad response"), {}, {}, {}])
        bridge.publish = Mock(side_effect=ConnectionError("queue full"))
        bridge.update_observations = Mock()
        ticks = []

        def wait(previous, period):
            ticks.append(previous)
            if len(ticks) == 2:
                bridge.stopped.set()
            return previous + period

        bridge.wait_for_poll = wait
        with self.assertLogs(level="WARNING"):
            bridge.run()
        bridge.update_observations.assert_called_once()
        self.assertEqual(len(ticks), 2)

    def test_placement_identity_is_unambiguous(self):
        placement = dict(
            valid=True, measurement_location="bench", configured_room="zone"
        )
        for raw in (
            '{"1":' + json.dumps(placement) + ',"1":' + json.dumps(placement) + "}",
            json.dumps({"1": placement, "01": placement}),
            json.dumps({"+1": placement}),
            json.dumps({" 1": placement}),
            json.dumps({"1": {**placement, "configured_room": " "}}),
            json.dumps({"1": {**placement, "measurement_location": " "}}),
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                node_placements(raw)

    def test_extreme_json_integer_fails_closed(self):
        self.assertFalse(finite_number(10**400))
        with self.assertRaises(ValueError):
            module_observations.number(10**400)

    def test_json_rejects_duplicate_fields_and_nonfinite_numbers(self):
        for raw in (
            '{"source":"simulated","source":"esp32"}',
            '{"node":{"node_id":1,"node_id":2}}',
            '{"age_ms":NaN}',
            '{"age_ms":Infinity}',
            '{"age_ms":1e400}',
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)

    def test_websocket_redirects_cannot_change_the_observation_source(self):
        for status in (300, 301, 302, 303, 307, 308):
            for destination in ("/other-stream", "ws://other.example.invalid/stream"):
                with self.subTest(status=status, destination=destination):
                    bridge = Bridge(
                        Mock(),
                        Config(
                            websocket_url="ws://collector.example.invalid/stream",
                            api_token="synthetic-only",
                        ),
                    )
                    client, server = socket.socketpair()
                    # Real HTTP parser, handshake, and redirect loop; only the
                    # network dial is replaced with an already-connected pair.
                    response = (
                        f"HTTP/1.1 {status} Redirect\r\nLocation: {destination}\r\n"
                        "Content-Length: 0\r\n\r\n".encode()
                    )
                    requests = []

                    def respond(server=server, response=response, requests=requests):
                        server.settimeout(2)
                        request = b""
                        while b"\r\n\r\n" not in request:
                            chunk = server.recv(4096)
                            if not chunk:
                                return
                            request += chunk
                        requests.append(request)
                        server.sendall(response)

                    server_thread = threading.Thread(target=respond, daemon=True)
                    with (
                        client,
                        server,
                        patch("socket.create_connection", return_value=client) as dial,
                        patch.object(
                            bridge.stopped,
                            "wait",
                            side_effect=lambda _, bridge=bridge: bridge.stopped.set(),
                        ),
                        self.assertLogs(level="WARNING") as logs,
                    ):
                        server_thread.start()
                        bridge.listen_falls()
                        server_thread.join(timeout=3)
                        self.assertFalse(server_thread.is_alive())
                        dial.assert_called_once()
                        self.assertEqual(
                            dial.call_args.kwargs["address"],
                            ("collector.example.invalid", 80),
                        )
                        self.assertEqual(
                            logs.output,
                            ["WARNING:root:Edge stream unavailable (ValueError)"],
                        )
                        self.assertEqual(len(requests), 1)
                        request = requests[0]
                        self.assertIn(b"GET /stream HTTP/1.1\r\n", request)
                        self.assertIn(
                            b"Authorization: Bearer synthetic-only\r\n", request
                        )


if __name__ == "__main__":
    unittest.main()
