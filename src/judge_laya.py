"""Use the locally stored Laya multilingual checkpoint for reply decisions."""

from __future__ import annotations

import os
from pathlib import Path

from judge import ACTION_MAP, INTENTS, RISK_LEVELS


REPLY_ACTIONS = {
    "skip": "这只是一个无需立即回应的陈述，暂时不回复也自然",
    "template": "一句固定的简短确认或感谢即可，不需要编写具体信息",
    "generate": "需要结合对话内容写一条有针对性的回复",
    "manual": "涉及责任、承诺、争议或敏感信息，用户应自己决定措辞",
}


def model_path() -> Path:
    configured = os.environ.get("LAYA_MODEL_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    # Source checkout: yun-laya/ sits beside models/. Packaged app uses the env path.
    return Path(__file__).resolve().parents[2] / "models" / "laya" / "multilingual"


class LayaJudge:
    name = "laya-local"

    def __init__(self, path: Path | None = None):
        self.path = path or model_path()
        self.agent = None

    @property
    def backend_label(self) -> str:
        return "本地 Laya"

    @property
    def load_status(self):
        return None

    def warm(self) -> None:
        if self.agent is not None:
            return
        required = ("model.safetensors", "rl_agent_config.json", "encoder/config.json",
                    "tokenizer/tokenizer.json")
        if not all((self.path / name).is_file() for name in required):
            raise FileNotFoundError(f"本地 Laya 权重不完整：{self.path}")
        import laya
        self.agent = laya.load(str(self.path), device="mps")

    def judge(self, message: str, context: str | None = None) -> dict:
        self.warm()
        state = f"{context}\n\n对方：{message}" if context else f"对方：{message}"
        questions = {
            "intent": {"type": "choice", "instructions": "对方这句话的主要意图是什么？",
                       "criteria": INTENTS},
            "risk": {"type": "score", "instructions": "现在直接回复这句话有多大风险？",
                     "criteria": RISK_LEVELS},
            "reply_action": {"type": "choice",
                             "instructions": "下一步应如何处理这条微信消息？",
                             "criteria": REPLY_ACTIONS},
        }
        answers = self.agent.predict(state, questions)["answers"]
        intent_ans = answers.get("intent") or {}
        risk_ans = answers.get("risk") or {}
        action_ans = answers.get("reply_action") or {}
        intent = intent_ans.get("choice", "闲聊")
        if intent not in INTENTS:
            intent = "闲聊"
        action = action_ans.get("choice", "generate")
        if action not in REPLY_ACTIONS:
            action = "generate"
        intent_probs = intent_ans.get("probabilities") or {}
        action_probs = action_ans.get("probabilities") or {}
        return {
            "intent": intent,
            "confidence": float(intent_probs.get(intent, 0)),
            "intent_probs": intent_probs,
            "risk": round(float(risk_ans.get("score") or 0), 1),
            "risk_probs": risk_ans.get("probabilities") or {},
            "reply_action": action,
            "reply_confidence": float(action_probs.get(action, 0)),
            "actions": ACTION_MAP.get(intent, []),
            "message": message,
            "backend": "本地 Laya",
        }

    def rank_candidates(self, message: str, intent: str,
                        candidates: list[str]) -> list[dict]:
        if not candidates:
            return []
        self.warm()
        criteria = {str(i): text for i, text in enumerate(candidates)}
        answer = self.agent.predict(
            f"收到的消息：{message}\n判断出的意图：{intent}",
            {"best": {"type": "choice", "instructions": "哪条回复最合适且没有编造事实？",
                      "criteria": criteria}})["answers"]["best"]
        probs = answer.get("probabilities") or {}
        ranked = [{"text": text, "prob": float(probs.get(str(i), 0))}
                  for i, text in enumerate(candidates)]
        ranked.sort(key=lambda item: -item["prob"])
        return ranked
