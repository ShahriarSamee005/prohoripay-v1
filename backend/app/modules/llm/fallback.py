"""Deterministic, LLM-free template fallback (English / Bangla / Banglish).

Builds a readable, safe-language explanation straight from the authoritative
structured object. This guarantees /api/explain ALWAYS returns usable text, even
when Groq is unavailable or its output fails the safety guard. Every branch covers
the key facts (balance/rate/trend or evidence, an advisory, and a human-review note)
and uses only numbers already present in the payload.
"""

from __future__ import annotations

from app.modules.llm.config import pool_label


def _fmt(n) -> str:
    try:
        return f"{int(round(float(n))):,}"
    except (TypeError, ValueError):
        return str(n)


def _num(n) -> str:
    """Compact number (drops a trailing .0) for inline mention."""
    try:
        f = float(n)
        return f"{int(f)}" if f == int(f) else f"{f:g}"
    except (TypeError, ValueError):
        return str(n)


# --------------------------------------------------------------------- forecast
def _needs_action(facts: dict) -> bool:
    state = facts.get("projection_state")
    if state == "at_floor":
        return True
    if state == "projected":
        return facts.get("status") in ("watch", "critical")
    return False  # filling / insufficient_data / intermittent -> just monitor


def _forecast_en(facts: dict) -> str:
    label = pool_label(facts.get("pool_id"), "en")
    current = _fmt(facts.get("current_balance"))
    state = facts.get("projection_state")
    mtd = facts.get("minutes_to_depletion")
    is_phys = facts.get("pool_id") == "physical_cash"

    balance = f"{label.capitalize()} is at {current} BDT"
    if state == "projected" and mtd is not None:
        situation = f"and at the current cash-out rate it may reach its safety reserve in about {_num(mtd)} minutes"
    elif state == "projected":
        situation = "and no near-term shortage is projected at the current rate"
    elif state == "filling":
        situation = "and is currently building up rather than depleting"
    elif state == "insufficient_data":
        situation = "with only limited recent activity, so this reading is low-confidence and is being monitored"
    elif state == "intermittent":
        situation = "with activity arriving in short bursts separated by quiet gaps, so it is being monitored rather than projected"
    else:  # at_floor
        situation = "at or below its safety reserve, which needs attention now"

    if _needs_action(facts):
        advisory = ("Consider arranging cash support before it runs low."
                    if is_phys else
                    f"Consider topping up {label} via the approved channel before it runs low.")
    else:
        advisory = "Continue to monitor for now."
    return f"{balance} {situation}. {advisory} A human should review and decide."


def _forecast_bn(facts: dict) -> str:
    label = pool_label(facts.get("pool_id"), "bn")
    current = _fmt(facts.get("current_balance"))
    state = facts.get("projection_state")
    mtd = facts.get("minutes_to_depletion")
    is_phys = facts.get("pool_id") == "physical_cash"

    balance = f"{label} এখন {current} BDT আছে"
    if state == "projected" and mtd is not None:
        situation = f"এবং বর্তমান নগদ-উত্তোলনের হারে প্রায় {_num(mtd)} মিনিটে নিরাপদ সীমায় পৌঁছাতে পারে"
    elif state == "projected":
        situation = "এবং বর্তমান হারে নিকট ভবিষ্যতে ঘাটতির সম্ভাবনা নেই"
    elif state == "filling":
        situation = "এবং এটি এখন কমছে না, বরং বাড়ছে"
    elif state == "insufficient_data":
        situation = "তবে সাম্প্রতিক লেনদেন কম, তাই তথ্য কম-নিশ্চিত এবং পর্যবেক্ষণ করা হচ্ছে"
    elif state == "intermittent":
        situation = "তবে লেনদেন থেমে থেমে আসছে, তাই অনুমান না করে পর্যবেক্ষণ করা হচ্ছে"
    else:
        situation = "যা নিরাপদ সীমায় বা তার নিচে—এখনই মনোযোগ প্রয়োজন"

    if _needs_action(facts):
        advisory = ("কমে যাওয়ার আগে নগদ টাকার ব্যবস্থা করার কথা বিবেচনা করুন।"
                    if is_phys else
                    f"কমে যাওয়ার আগে অনুমোদিত চ্যানেলে {label} ব্যালেন্স যোগ করার কথা বিবেচনা করুন।")
    else:
        advisory = "আপাতত পর্যবেক্ষণ চালিয়ে যান।"
    return f"{balance} {situation}। {advisory} একজন মানুষ বিষয়টি পর্যালোচনা করে সিদ্ধান্ত নিন।"


def _forecast_banglish(facts: dict) -> str:
    label = pool_label(facts.get("pool_id"), "banglish")
    current = _fmt(facts.get("current_balance"))
    state = facts.get("projection_state")
    mtd = facts.get("minutes_to_depletion")
    is_phys = facts.get("pool_id") == "physical_cash"

    balance = f"{label} e ekhon {current} BDT ache"
    if state == "projected" and mtd is not None:
        situation = f"ebong ekhonkar cash-out hare prai {_num(mtd)} minute er moddhe safe reserve e chole aste pare"
    elif state == "projected":
        situation = "ebong ekhonkar hare kache kono ghatti dekha jacche na"
    elif state == "filling":
        situation = "ebong eta ekhon komche na, borong barche"
    elif state == "insufficient_data":
        situation = "kintu recent lenden kom, tai eta low-confidence r ekhon monitor kora hocche"
    elif state == "intermittent":
        situation = "kintu lenden theme theme asche, tai project na kore monitor kora hocche"
    else:
        situation = "ja safe reserve er kache ba nicher—ekhoni nojor dorkar"

    if _needs_action(facts):
        advisory = ("Kome jawar age cash er bebostha korar kotha bhabun."
                    if is_phys else
                    f"Kome jawar age approved channel e {label} balance add korar kotha bhabun.")
    else:
        advisory = "Apatoto monitor kore jan."
    return f"{balance} {situation}. {advisory} Ekjon manush review kore siddhanto nin."


# ------------------------------------------------------------------------ alert
def _alert_signal(facts: dict) -> tuple[str, str] | None:
    """Best numeric detail (observed, baseline) for a short in-language hint."""
    observed = facts.get("observed") or {}
    baseline = facts.get("baseline") or {}
    for key in ("txn_per_min",):
        if key in observed and key in baseline:
            return _num(observed[key]), _num(baseline[key])
    if "minutes_to_depletion" in observed and observed["minutes_to_depletion"] is not None:
        return _num(observed["minutes_to_depletion"]), ""
    return None


def _alert_en(facts: dict) -> str:
    who = pool_label(facts.get("provider") or facts.get("pool_id"), "en")
    conf = _num(round(float(facts.get("confidence", 0.0)) * 100))
    lead = ("There is unusual activity that needs review"
            if facts.get("type") == "anomaly" else
            "There is liquidity pressure that needs attention")
    evidence = facts.get("evidence") or []
    ev = f" Evidence: {'; '.join(evidence)}." if evidence else ""
    return (f"{lead} on {who}.{ev} Confidence is about {conf}%. "
            "Please review with the agent before any decision; a human should decide.")


def _alert_bn(facts: dict) -> str:
    who = pool_label(facts.get("provider") or facts.get("pool_id"), "bn")
    conf = _num(round(float(facts.get("confidence", 0.0)) * 100))
    lead = (f"{who}-এ অস্বাভাবিক কার্যকলাপ দেখা গেছে যা পর্যালোচনা প্রয়োজন"
            if facts.get("type") == "anomaly" else
            f"{who}-এ তারল্যের চাপ দেখা যাচ্ছে যা মনোযোগ প্রয়োজন")
    sig = _alert_signal(facts)
    hint = ""
    if sig and facts.get("type") == "anomaly":
        hint = f" পর্যবেক্ষণ: প্রতি মিনিটে প্রায় {sig[0]} (স্বাভাবিক {sig[1]})।"
    elif sig:
        hint = f" প্রায় {sig[0]} মিনিটের হিসাব।"
    return (f"{lead}।{hint} নিশ্চয়তা প্রায় {conf}%। "
            "এজেন্টের সাথে যাচাই করে একজন মানুষ সিদ্ধান্ত নিন।")


def _alert_banglish(facts: dict) -> str:
    who = pool_label(facts.get("provider") or facts.get("pool_id"), "banglish")
    conf = _num(round(float(facts.get("confidence", 0.0)) * 100))
    lead = (f"{who} e oshadharon activity dekha gche, review dorkar"
            if facts.get("type") == "anomaly" else
            f"{who} e liquidity chap dekha jacche, attention dorkar")
    sig = _alert_signal(facts)
    hint = ""
    if sig and facts.get("type") == "anomaly":
        hint = f" Observe: prai {sig[0]}/min (normal {sig[1]})."
    elif sig:
        hint = f" Prai {sig[0]} minute er hisab."
    return (f"{lead}.{hint} Confidence prai {conf}%. "
            "Agent er sathe jachai kore ekjon manush siddhanto nin.")


# ------------------------------------------------------------------- dispatch
_FORECAST = {"en": _forecast_en, "bn": _forecast_bn, "banglish": _forecast_banglish}
_ALERT = {"en": _alert_en, "bn": _alert_bn, "banglish": _alert_banglish}


def render(kind: str, lang: str, facts: dict) -> str:
    """Deterministic safe explanation for the given kind/lang/facts."""
    table = _ALERT if kind == "alert" else _FORECAST
    builder = table.get(lang, table["en"])
    return builder(facts)
