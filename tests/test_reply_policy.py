"""Verify that local decisions actually gate paid generation."""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reply_policy import plan_reply
from support_hud import Harness, HUD, block


class ReplyPolicyTests(unittest.TestCase):
    def test_high_risk_never_generates(self):
        plan = plan_reply({"risk": 8, "intent": "批评", "reply_action": "generate"})
        self.assertEqual(plan.action, "manual")

    def test_work_request_cannot_be_silently_skipped(self):
        plan = plan_reply({"risk": 2, "intent": "催进度", "reply_action": "skip",
                           "reply_confidence": 0.9})
        self.assertEqual(plan.action, "generate")

    def test_simple_praise_uses_local_template(self):
        plan = plan_reply({"risk": 1, "intent": "夸奖", "reply_action": "template"})
        self.assertEqual(plan.action, "template")
        self.assertTrue(plan.text)

    def test_hud_waits_for_decision_before_generation(self):
        h = Harness()
        h._reply_worker = __import__("threading").local()
        h._reply_epoch = 1
        h._reply_key = ("chat", "今天跟一下")
        h._wechat_frontmost = True
        h._paused = False
        h.slot_tones = ["高情商话术", "不用", "不用"]
        h.generator = Mock()
        h._finish_generate = Mock()
        h._model_lock = __import__("threading").Lock()
        h._gen_epoch = 0
        h.performSelectorOnMainThread_withObject_waitUntilDone_ = Mock()
        msgs = [Mock(text="今天跟一下", sender=None, side="them")]
        verdict = {"message": "今天跟一下", "intent": "派活", "risk": 2,
                   "reply_action": "generate", "actions": ["问清交付标准"]}
        h._reply_task(1, h._route_reply, msgs[0], msgs, verdict, time.perf_counter())
        h.generator.generate.assert_called_once()
        args, kwargs = h.generator.generate.call_args
        self.assertEqual(args[1], "派活")
        self.assertEqual(kwargs["guidance"], "问清交付标准")
        h.generator.reset_mock()
        quiet = {**verdict, "intent": "闲聊", "reply_action": "skip",
                 "reply_confidence": 0.8}
        h._reply_task(1, h._route_reply, msgs[0], msgs, quiet, time.perf_counter())
        h.generator.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
