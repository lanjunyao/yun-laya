"""A chat-only WeChat window puts incoming bubbles at the left window edge."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from perception import TextBlock, WindowInfo, extract_messages, read_conversation


class FullscreenChatTests(unittest.TestCase):
    def test_short_left_edge_body_is_not_dropped_as_sender_name(self):
        hello = TextBlock("你好", 1.0, .05, .28, .06, .021)
        messages = extract_messages([hello], input_top=.76, pane_left=0)
        self.assertEqual([(m.side, m.text) for m in messages], [("them", "你好")])

    def test_left_edge_incoming_message_is_extracted_when_composer_spans_window(self):
        window = WindowInfo(1, 7, "WeChat", 0, 0, 2202, 1554)
        hello = TextBlock("你好", 1.0, .05, .28, .06, .035)
        with patch("perception.find_wechat_window", return_value=window), \
             patch("perception.capture_image", return_value=object()), \
             patch("input_region.input_outline", return_value=(.01, .76, .98, .24)), \
             patch("perception._fingerprint", return_value=b"frame") as fingerprint, \
             patch("perception.ocr_image", return_value=[hello]) as ocr_image:
            result = read_conversation()
        self.assertTrue(result["ok"])
        self.assertLess(ocr_image.call_args.kwargs["pane_left"], .05)
        self.assertLess(fingerprint.call_args.args[2], .05)
        self.assertEqual([(m.side, m.text) for m in result["messages"]], [("them", "你好")])


if __name__ == "__main__":
    unittest.main()
