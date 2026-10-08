"""Teach-back quiz built from verified, signed-off sentences.

No model is involved: the right answer is the exact sentence the reviewer
approved, and the wrong answers come from fixed, pre-translated templates. A
quiz cannot hallucinate.
"""

import hashlib
import random

from . import lexicon

T = {
    "en": {
        "med_q": "Which is right about {drug}?",
        "warn_q": "Which of these means you should get help?",
        "appt_q": "What did your care team say about your next visit?",
        "med_wrong": {
            "keep": "Keep taking {drug} the same way as before.",
            "stop": "Stop taking {drug} today.",
            "prn": "Take {drug} only when you feel unwell.",
            "double": "If you miss a dose of {drug}, take two next time.",
        },
        "warn_wrong": ["Feeling hungry before dinner.", "Wanting to sleep at night.",
                       "Feeling happy to be home."],
        "appt_wrong": ["You do not need any more visits.", "Only come back if you feel much worse."],
    },
    "es": {
        "med_q": "¿Qué es correcto sobre {drug}?",
        "warn_q": "¿Cuál de estas señales significa que debe pedir ayuda?",
        "appt_q": "¿Qué le dijo su equipo médico sobre su próxima cita?",
        "med_wrong": {
            "keep": "Siga tomando {drug} igual que antes.",
            "stop": "Deje de tomar {drug} hoy.",
            "prn": "Tome {drug} solo cuando se sienta mal.",
            "double": "Si olvida una dosis de {drug}, tome dos la próxima vez.",
        },
        "warn_wrong": ["Tener hambre antes de la cena.", "Tener sueño por la noche.",
                       "Sentirse feliz de estar en casa."],
        "appt_wrong": ["No necesita más citas.", "Vuelva solo si se siente mucho peor."],
    },
    "it": {
        "med_q": "Cosa è corretto su {drug}?",
        "warn_q": "Quale di questi segnali significa che deve chiedere aiuto?",
        "appt_q": "Cosa le ha detto il team di cura sulla prossima visita?",
        "med_wrong": {
            "keep": "Continui a prendere {drug} come prima.",
            "stop": "Smetta di prendere {drug} oggi.",
            "prn": "Prenda {drug} solo quando si sente male.",
            "double": "Se dimentica una dose di {drug}, la volta dopo ne prenda due.",
        },
        "warn_wrong": ["Avere fame prima di cena.", "Avere sonno la sera.",
                       "Essere contento di essere a casa."],
        "appt_wrong": ["Non servono altre visite.", "Torni solo se si sente molto peggio."],
    },
    "vi": {
        "med_q": "Điều nào đúng về thuốc {drug}?",
        "warn_q": "Dấu hiệu nào sau đây có nghĩa là bạn cần tìm trợ giúp?",
        "appt_q": "Nhóm chăm sóc đã nói gì về lần khám tiếp theo của bạn?",
        "med_wrong": {
            "keep": "Tiếp tục uống {drug} như trước đây.",
            "stop": "Ngừng uống {drug} từ hôm nay.",
            "prn": "Chỉ uống {drug} khi bạn thấy không khỏe.",
            "double": "Nếu quên một liều {drug}, lần sau uống gấp đôi.",
        },
        "warn_wrong": ["Thấy đói trước bữa tối.", "Buồn ngủ vào ban đêm.", "Vui vì được về nhà."],
        "appt_wrong": ["Bạn không cần tái khám nữa.", "Chỉ quay lại nếu bạn thấy tệ hơn nhiều."],
    },
    "zh": {
        "med_q": "关于{drug}，哪一项是正确的？",
        "warn_q": "以下哪一项表示您需要寻求帮助？",
        "appt_q": "医护团队对您下次就诊是怎么说的？",
        "med_wrong": {
            "keep": "和以前一样继续服用{drug}。",
            "stop": "从今天起停用{drug}。",
            "prn": "只在不舒服时服用{drug}。",
            "double": "如果漏服一次{drug}，下次服用两倍剂量。",
        },
        "warn_wrong": ["晚饭前感到饿。", "晚上想睡觉。", "回家后感到开心。"],
        "appt_wrong": ["您不需要再复诊。", "只有感觉更差时才回来。"],
    },
    "fr": {
        "med_q": "Qu'est-ce qui est juste à propos de {drug} ?",
        "warn_q": "Lequel de ces signes veut dire que vous devez demander de l'aide ?",
        "appt_q": "Qu'a dit votre équipe de soins sur votre prochain rendez-vous ?",
        "med_wrong": {
            "keep": "Continuez à prendre {drug} comme avant.",
            "stop": "Arrêtez de prendre {drug} aujourd'hui.",
            "prn": "Prenez {drug} seulement quand vous vous sentez mal.",
            "double": "Si vous oubliez une dose de {drug}, prenez-en deux la fois suivante.",
        },
        "warn_wrong": ["Avoir faim avant le dîner.", "Avoir sommeil le soir.",
                       "Être content d'être à la maison."],
        "appt_wrong": ["Vous n'avez plus besoin de rendez-vous.",
                       "Revenez seulement si vous allez beaucoup plus mal."],
    },
}

WRONG_BY_ACTION = {
    "stop": ["keep", "prn"],
    "hold": ["keep", "double"],
    "continue": ["stop", "prn"],
    "new": ["prn", "double"],
    "changed": ["keep", "double"],
}


def build_quiz(case: dict, max_questions: int = 4) -> list[dict]:
    lang = case["language"] if case["language"] in T else "en"
    t = T[lang]
    facts = {f["id"]: f for f in case["facts"]}
    sentences = [s for s in case["sentences"] if not s.get("removed")]
    rng = random.Random(int(hashlib.sha256(case["id"].encode()).hexdigest(), 16))

    def shown(s: dict) -> str:
        return s.get("text_tl") or s["text_en"] if lang != "en" else s["text_en"]

    questions, used = [], set()
    order = {"medication": 0, "warning_sign": 1, "follow_up": 2}
    candidates = sorted(
        (f for f in facts.values() if f.get("kind") in order and (f.get("risk") == "high" or f["kind"] == "follow_up")),
        key=lambda f: (order[f["kind"]], f["id"]))
    for f in candidates:
        if len(questions) >= max_questions:
            break
        citing = [s for s in sentences if f["id"] in s.get("fact_ids", [])]
        if f["kind"] == "medication":
            drug = (f.get("drug") or "").split()[0].lower()
            canon = lexicon.canonical_drug(drug)
            citing = [s for s in citing if canon in lexicon.drugs_in(s["text_en"])] or citing
        if not citing or citing[0]["id"] in used:
            continue
        right = citing[0]
        used.add(right["id"])
        if f["kind"] == "medication":
            wrong = [t["med_wrong"][k].format(drug=drug) for k in WRONG_BY_ACTION.get(f.get("med_action"), ["prn", "double"])]
            q = t["med_q"].format(drug=drug)
        elif f["kind"] == "warning_sign":
            wrong = rng.sample(t["warn_wrong"], 2)
            q = t["warn_q"]
        else:
            wrong = list(t["appt_wrong"])
            q = t["appt_q"]
        options = [{"text": shown(right), "correct": True}] + [{"text": w, "correct": False} for w in wrong]
        rng.shuffle(options)
        questions.append({"id": f"Q{len(questions) + 1}", "fact_id": f["id"], "sentence_id": right["id"],
                          "question": q, "options": options, "answer": None})
    return questions
