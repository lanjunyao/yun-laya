"""Deterministic guardrails around Laya's decision; no generation happens here."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReplyPlan:
    action: str  # skip | template | generate | manual
    reason: str
    text: str = ""
    variants: dict[str, str] = field(default_factory=dict)


TEMPLATES = {
    "夸奖": {
        "高情商": "谢谢你的认可，我很开心",
        "阴阳怪气": "哎呀，这下被你发现我认真了",
        "一本正经": "谢谢认可，我会继续做好",
    },
    "问候": {
        "高情商": "你好呀，最近怎么样？",
        "阴阳怪气": "哟，终于想起我啦？",
        "一本正经": "你好，请说",
    },
}


def plan_reply(verdict: dict) -> ReplyPlan:
    risk = float(verdict.get("risk") or 0)
    intent = verdict.get("intent", "")
    action = verdict.get("reply_action", "generate")
    if risk >= 7 or action == "manual":
        return ReplyPlan("manual", "风险较高，建议自己斟酌回复")
    # A missed work request is worse than spending one generation call. Laya's local
    # classifier can disagree with the intent classifier, so only quiet chat may skip.
    if action == "skip" and intent == "闲聊" and float(verdict.get("reply_confidence") or 0) >= 0.5:
        return ReplyPlan("skip", "这条消息可以暂时不回")
    templates = (TEMPLATES["夸奖"] if intent == "夸奖" else
                 TEMPLATES["问候"] if intent == "闲聊" and
                 verdict.get("message", "").strip() in {"你好", "你好呀", "嗨", "哈喽", "hi", "Hi"}
                 else None)
    if action == "template" and templates:
        return ReplyPlan("template", "三种本地回复，无需调用生成模型",
                         templates["高情商"], templates)
    return ReplyPlan("generate", "结合 Laya 判断生成三类候选")
