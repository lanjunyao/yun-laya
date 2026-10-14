"""All actual replies use the same three named styles."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import styles
from generate import Generator
from reply_policy import plan_reply


EXPECTED = ["高情商", "阴阳怪气", "一本正经"]


class ThreeReplyStylesTests(unittest.TestCase):
    def test_generation_uses_one_request_for_three_categories(self):
        self.assertEqual(styles.DEFAULT_SLOTS, EXPECTED)
        generator = Generator()
        with patch.object(generator, "_creds_or_load", return_value=("local", "key", "model")), \
             patch.object(generator, "_call", return_value=(
                 '{"高情商":"谢谢你提醒，我这就确认",'
                 '"阴阳怪气":"哟，这提醒来得真及时",'
                 '"一本正经":"收到，我会核实"}')) as call:
            result = generator.generate("请确认一下", "派活", EXPECTED)
        call.assert_called_once()
        self.assertEqual([(g["tone"], len(g["texts"])) for g in result["groups"]],
                         [(style, 1) for style in EXPECTED])
        self.assertEqual(result["error"], "")

    def test_local_template_has_same_three_categories(self):
        plan = plan_reply({"message": "谢谢你", "risk": 1,
                           "intent": "夸奖", "reply_action": "template"})
        self.assertEqual(plan.action, "template")
        self.assertEqual(list(plan.variants), EXPECTED)
        self.assertTrue(all(plan.variants.values()))

    def test_labelled_lines_keep_categories_and_reject_missing_one(self):
        parsed = Generator._parse_three_styles(
            "1. 高情商：谢谢提醒\n2. 阴阳怪气：哟，提醒得真及时\n3. 一本正经：收到")
        self.assertEqual(list(parsed), EXPECTED)
        self.assertEqual(parsed["一本正经"], "收到")
        self.assertEqual(Generator._parse_three_styles(
            "高情商：谢谢提醒\n高情商：知道了\n一本正经：收到"), {})


if __name__ == "__main__":
    unittest.main()
