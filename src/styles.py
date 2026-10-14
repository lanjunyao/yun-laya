"""Built-in 话术 presets — one label + one instruction per tone.

These are what the generation prompt asks the model to write in; the user picks up to
MAX_SLOTS of them from the HUD. Keeping them here (rather than inline in the prompt) means
one place to add a tone, and lets the parser strip any label the model echoes back.

Each `prompt` is written as a direct instruction to the model: say what the tone IS, and
what it must not become. Vague one-word tones ("幽默") produce generic replies — the
useful part is the constraint.
"""

from __future__ import annotations

import re

import userconfig

# Every reply surface has the same three categories, one candidate each.
MAX_SLOTS = 3
PER_TONE = 1
BUILTIN: dict[str, str] = {
    "高情商": (
        "先照顾对方感受，再给清楚的回应；温和自然，不替用户承诺没有确认的事。"
    ),
    "阴阳怪气": (
        "带一点轻微、可直接发送的反讽或俏皮反问；不辱骂、不人身攻击，"
        "涉及严肃事务时保持分寸。"
    ),
    "一本正经": (
        "只说事实、决定和下一步；语气克制、简洁明确，不寒暄、不玩梗。"
    ),
}
DEFAULT_SLOTS: list[str] = ["高情商", "阴阳怪气", "一本正经"]
NONE_LABEL = "不用"  # Retained for old configuration compatibility.
CUSTOM_VAR = "LAYA_TONES"  # Only descriptions of the three fixed categories may change.


def _custom_tones() -> dict[str, str]:
    """Override wording for one of the three fixed categories via LAYA_TONES."""
    raw = userconfig.get(CUSTOM_VAR)
    out: dict[str, str] = {}
    for part in (raw or "").split("|"):
        name, sep, desc = part.partition("=")
        name, desc = name.strip(), desc.strip()
        if sep and name in BUILTIN and desc:
            out[name] = desc
    return out


CUSTOM: dict[str, str] = _custom_tones()
PRESETS: dict[str, str] = {**BUILTIN, **CUSTOM}

def _label_alternation() -> str:
    """The labels as one regex alternative, with spaces made optional.

    "贴吧老哥 v1.0" is written with a space in the dropdown but the model may echo it
    without one ("贴吧老哥v1.0：") — matching the space loosely costs nothing and avoids a
    label that leaks through only sometimes.
    """
    escaped = (re.escape(k).replace(r"\ ", r"\s*") for k in sorted(PRESETS, key=len, reverse=True))
    return "|".join(escaped)


_LABEL_RE = re.compile(
    rf"^[*_#\s]*(?:{_label_alternation()})[^，。！？；、,.!?;：:]{{0,4}}[*_#\s]*[:：]\s*")


def labels() -> list[str]:
    """All preset labels, in dropdown order."""
    return list(PRESETS)


def strip_label(line: str) -> str:
    """Remove a leading preset label the model echoed back, e.g. "贴吧老哥 v1.0：好的哥".

    The model is told not to label its lines, and usually complies — but the prompt itself
    shows it these labels, so now and then it echoes one. Because the labels are data, they
    are stripped from the same place they are defined: adding a tone here cannot silently
    break the parser the way a hardcoded list would.
    """
    return _LABEL_RE.sub("", line)
