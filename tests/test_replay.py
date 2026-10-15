# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch

from ruview_home_assistant.replay import render_html, replay, synthetic_frames


class ReplayTests(unittest.TestCase):
    def test_offline_replay_exercises_production_gates(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            results = [replay(frame) for frame in synthetic_frames()]
        self.assertEqual(
            [r["occupancy_entity"] for r in results],
            ["ON", "ON", "OFF", "unavailable", "unavailable"],
        )
        self.assertTrue(all(r["synthetic"] for r in results))
        self.assertTrue(
            all(
                not m["retain"]
                for r in results
                for m in r["publications"]
                if m["topic"].endswith("/state")
            )
        )
        self.assertEqual(results, [replay(frame) for frame in synthetic_frames()])

    def test_html_escapes_user_labels(self):
        result = replay(next(synthetic_frames()))
        result["label"] = "<script>bad()</script>"
        page = render_html([result])
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
