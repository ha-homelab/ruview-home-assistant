# SPDX-License-Identifier: MIT
"""Use Paho's real queue and CONNACK handler without a socket or broker."""

import json
import struct
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt

from ruview_home_assistant import bridge as implementation
from ruview_home_assistant.config import Config


class ReconnectTests(unittest.TestCase):
    def setUp(self):
        no_socket = patch(
            "socket.socket", side_effect=AssertionError("unexpected socket")
        )
        no_socket.start()
        self.addCleanup(no_socket.stop)
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="synthetic"
        )
        config = Config(
            node_ids=(1,),
            node_placements_json=json.dumps(
                {
                    "1": {
                        "valid": True,
                        "measurement_location": "synthetic",
                        "configured_room": "synthetic",
                    }
                }
            ),
        )
        self.bridge = implementation.Bridge(self.client, config)
        self.bridge.fall_thread = Mock()
        self.bridge.module_thread = Mock()
        self.bridge.run = Mock()
        # Install the actual application's callbacks. Only lifecycle operations
        # are replaced; no test copy of the connection callback is used.
        with (
            patch.object(implementation.Config, "from_env", return_value=config),
            patch.object(implementation, "Bridge", return_value=self.bridge),
            patch.object(mqtt, "Client", return_value=self.client),
            patch.object(implementation.signal, "signal"),
            patch.object(implementation.logging, "basicConfig"),
            patch.object(self.client, "connect_async"),
            patch.object(self.client, "loop_start"),
            patch.object(self.client, "loop_stop"),
            patch.object(self.client, "disconnect"),
        ):
            implementation.main([])
        self.bridge.last_discovery = 100
        self.client._send_publish = Mock(return_value=mqtt.MQTT_ERR_SUCCESS)
        self.client.loop_write = Mock(return_value=mqtt.MQTT_ERR_SUCCESS)
        self.client.subscribe = Mock(return_value=(mqtt.MQTT_ERR_SUCCESS, 1))
        self.reconnect()
        self.bridge.rediscover.clear()
        self.client.subscribe.reset_mock()

    def current(self, presence="ON"):
        return {
            1: {
                "presence": presence,
                "motion": presence,
                "classification": "present_moving" if presence == "ON" else "absent",
                "signal": -60,
                "csi_age_ms": 0,
                "inference_age_ms": 0,
                "snapshot_age_ms": 0,
            }
        }

    def reconnect(self, reason=0):
        # These are the real queue reset and packet-processing paths. The raw
        # CONNACK and mocked transport replace only a network connection.
        self.client._messages_reconnect_reset()
        self.client.on_pre_connect(self.client, None)
        self.client._in_packet["command"] = 0x20
        self.client._in_packet["packet"] = bytes((0, reason))
        self.client._send_publish.reset_mock()
        with patch.object(mqtt, "time_func", return_value=1000):
            return self.client._handle_connack()

    def acknowledge_all(self):
        for mid in list(self.client._out_messages):
            self.client._in_packet["command"] = 0x40
            self.client._in_packet["packet"] = struct.pack("!H", mid)
            self.assertEqual(
                self.client._handle_pubackcomp("PUBACK"), mqtt.MQTT_ERR_SUCCESS
            )
        self.assertFalse(self.client._out_messages)
        self.assertEqual(self.client._inflight_messages, 0)

    def test_old_primary_state_and_online_leases_are_not_replayed(self):
        self.bridge.update(self.current(), observed_at=100, clock=lambda: 100)
        queued = list(self.client._out_messages.values())
        self.assertEqual(len(queued), 6)
        self.assertTrue(
            any(
                message.topic.endswith("/state") and b'"ON"' in message.payload
                for message in queued
            )
        )
        self.acknowledge_all()
        self.assertTrue(
            any(message.retain and message.payload == b"online" for message in queued)
        )

        self.assertEqual(self.reconnect(), mqtt.MQTT_ERR_SUCCESS)
        self.client._send_publish.assert_not_called()
        self.assertFalse(self.client._out_messages)
        self.assertTrue(self.bridge.rediscover.is_set())
        self.client.subscribe.assert_called_once_with("homeassistant/status", qos=1)

        # A fresh acquisition can publish normally after the queue is discarded.
        self.bridge.update(self.current("OFF"), observed_at=1000, clock=lambda: 1000)
        state_messages = [
            call.args[2]
            for call in self.client._send_publish.call_args_list
            if call.args[1] == b"ruview/home/node1/state"
        ]
        self.assertEqual(len(state_messages), 1)
        self.assertEqual(json.loads(state_messages[0])["presence"], "OFF")
        self.assertTrue(
            any(
                call.args[1].endswith(b"/config")
                for call in self.client._send_publish.call_args_list
            )
        )

    def test_edge_modules_and_discovery_are_also_discarded_for_regeneration(self):
        self.bridge.edge_falls.ingest(
            {"type": "edge_vitals", "node_id": 1, "fall_detected": True}, 100
        )
        self.bridge.update(self.current(), observed_at=100, clock=lambda: 100)
        self.bridge.announce()
        self.bridge.publish(
            "ruview/home/node1/modules/observation", {"state": "experimental"}
        )
        topics = {message.topic for message in self.client._out_messages.values()}
        self.assertIn("ruview/home/node1/fall/state", topics)
        self.assertIn("ruview/home/node1/modules/observation", topics)
        self.assertTrue(any(topic.endswith("/config") for topic in topics))

        self.assertEqual(self.reconnect(), mqtt.MQTT_ERR_SUCCESS)
        self.client._send_publish.assert_not_called()
        self.assertFalse(self.client._out_messages)
        self.assertTrue(self.bridge.rediscover.is_set())

    def test_publish_rejected_as_disconnected_can_still_leave_a_pending_message(self):
        self.client._send_publish.return_value = mqtt.MQTT_ERR_NO_CONN
        with self.assertRaises(ConnectionError):
            self.bridge.publish("ruview/home/node1/state", {"presence": "ON"})
        self.assertEqual(len(self.client._out_messages), 1)

        self.client._send_publish.return_value = mqtt.MQTT_ERR_SUCCESS
        self.assertEqual(self.reconnect(), mqtt.MQTT_ERR_SUCCESS)
        self.client._send_publish.assert_not_called()
        self.assertFalse(self.client._out_messages)

    def test_rejected_connection_does_not_discard_or_announce_success(self):
        self.bridge.publish("ruview/home/node1/state", {"presence": "ON"})
        pending = list(self.client._out_messages)
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.reconnect(reason=5), mqtt.MQTT_ERR_CONN_REFUSED)
        self.assertEqual(list(self.client._out_messages), pending)
        self.client._send_publish.assert_not_called()
        self.client.subscribe.assert_not_called()
        self.assertFalse(self.bridge.rediscover.is_set())

    def test_paho_connected_before_callback_does_not_enable_publication(self):
        self.client.on_pre_connect(self.client, None)
        self.assertTrue(self.client.is_connected())
        with self.assertRaisesRegex(ConnectionError, "not ready"):
            self.bridge.publish("ruview/home/node1/state", {"presence": "ON"})
        self.assertFalse(self.client._out_messages)
        self.assertEqual(self.client._inflight_messages, 0)

    def test_disconnect_immediately_closes_the_publication_gate(self):
        self.client.on_disconnect(self.client, None, None, None, None)
        with self.assertRaisesRegex(ConnectionError, "not ready"):
            self.bridge.publish("ruview/home/node1/state", {"presence": "ON"})
        self.assertFalse(self.client._out_messages)

    def test_preconnect_waits_for_a_writer_that_already_passed_the_old_gate(self):
        entered, release = threading.Event(), threading.Event()
        connecting, prepared = threading.Event(), threading.Event()
        original_publish = self.client.publish

        def held_publish(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise AssertionError("test did not release old publication")
            return original_publish(*args, **kwargs)

        def publish_old():
            # Paho has already closed the old socket before pre-connect.
            with self.assertRaises(ConnectionError):
                self.bridge.publish("ruview/home/node1/state", {"presence": "ON"})

        def prepare_connection():
            self.client._messages_reconnect_reset()
            connecting.set()
            self.client.on_pre_connect(self.client, None)
            prepared.set()

        self.client._send_publish.return_value = mqtt.MQTT_ERR_NO_CONN
        with (
            patch.object(self.client, "publish", side_effect=held_publish),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            publisher = pool.submit(publish_old)
            try:
                self.assertTrue(entered.wait(2))
                preparation = pool.submit(prepare_connection)
                self.assertTrue(connecting.wait(2))
                self.assertFalse(prepared.wait(0.05))
            finally:
                release.set()
            publisher.result(timeout=2)
            preparation.result(timeout=2)
        self.assertTrue(prepared.is_set())
        self.assertFalse(self.bridge._connection_ready.is_set())
        self.assertEqual(len(self.client._out_messages), 1)
        self.assertEqual(self.client._inflight_messages, 0)
        self.client._send_publish.return_value = mqtt.MQTT_ERR_SUCCESS
        self.reconnect()
        self.bridge.publish("ruview/home/node1/state", {"presence": "OFF"})
        self.assertEqual(len(self.client._out_messages), 1)
        self.acknowledge_all()

    def test_fresh_publication_during_discard_waits_and_can_fully_drain(self):
        self.bridge.publish("ruview/home/node1/state", {"presence": "ON"})
        entered, release = threading.Event(), threading.Event()
        attempted, completed = threading.Event(), threading.Event()
        original_drop = self.client.drop_out_messages

        def held_drop():
            entered.set()
            if not release.wait(2):
                raise AssertionError("test did not release discard")
            return original_drop()

        def publish_fresh():
            try:
                attempted.set()
                self.bridge.publish("ruview/home/node1/state", {"presence": "OFF"})
            finally:
                completed.set()

        with (
            patch.object(self.client, "drop_out_messages", side_effect=held_drop),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            connection = pool.submit(self.reconnect)
            try:
                self.assertTrue(entered.wait(2))
                publisher = pool.submit(publish_fresh)
                self.assertTrue(attempted.wait(2))
                self.assertFalse(completed.wait(0.05))
            finally:
                release.set()
            self.assertEqual(connection.result(timeout=2), mqtt.MQTT_ERR_SUCCESS)
            publisher.result(timeout=2)
        pending = list(self.client._out_messages.values())
        self.assertEqual(len(pending), 1)
        self.assertEqual(json.loads(pending[0].payload), {"presence": "OFF"})
        self.assertEqual(self.client._inflight_messages, 1)
        self.acknowledge_all()


if __name__ == "__main__":
    unittest.main()
