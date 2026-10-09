"""Build canned model outputs (clean and mutated) for the red-team cases.

python3 build.py  -> writes fixtures/<case>/<variant>/<stage>.json and fixtures/manifest.json
Variants: clean, mutated (all mutations of the case), and one per mutation (e.g. A-M1).
"""
import copy, importlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sources import CASES  # noqa: E402

MODULES = ["case_af_hoa_vi", "case_dm_chen_zh", "case_copd_moreau_fr",
           "case_asthma_mateo_es", "case_appy_huy_vi"]


def build(mod, muts):
    facts = copy.deepcopy(mod.FACTS)
    draft = [list(t) for t in mod.DRAFT]
    judge = {s[0]: ("supported", "Matches the cited facts.") for s in draft}
    judge.update(mod.JUDGE)
    tl_patch, back_patch = {}, {}
    for m in muts:
        for fid, fields in (m.get("facts") or {}).items():
            next(f for f in facts if f["id"] == fid).update(fields)
        facts = [f for f in facts if f["id"] not in m.get("drop_facts", [])]
        for sid, (en, tl, back) in (m.get("draft") or {}).items():
            row = next(r for r in draft if r[0] == sid)
            row[2], row[4], row[5] = en, tl, back
        draft = [r for r in draft if r[0] not in m.get("drop_sentences", [])]
        for add in m.get("add", []):
            pos = next(i for i, r in enumerate(draft) if r[0] == m["after"]) + 1
            draft.insert(pos, list(add))
        tl_patch.update(m.get("tl") or {})
        back_patch.update(m.get("back") or {})
        judge.update(m.get("judge") or {})
    out = {
        "facts": {"facts": facts},
        "draft": {"sentences": [{"id": r[0], "section": r[1], "text": r[2], "fact_ids": r[3]} for r in draft]},
        "translate": {"items": [{"id": r[0], "text": tl_patch.get(r[0], r[4])} for r in draft]},
        "back_translate": {"items": [{"id": r[0], "text": back_patch.get(r[0], r[5])} for r in draft]},
        "judge": {"verdicts": [{"id": r[0], "verdict": judge[r[0]][0], "reason": judge[r[0]][1]} for r in draft]},
    }
    return out


def main():
    manifest = {}
    for name in MODULES:
        mod = importlib.import_module(name)
        case = CASES[mod.CASE_ID]
        variants = {"clean": [], "mutated": list(mod.MUTATIONS)}
        for m in mod.MUTATIONS:
            variants[m["id"]] = [m]
        for v, muts in variants.items():
            d = HERE / "fixtures" / mod.CASE_ID / v
            d.mkdir(parents=True, exist_ok=True)
            for stage, obj in build(mod, muts).items():
                (d / f"{stage}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1))
        manifest[mod.CASE_ID] = {
            "title": case["title"], "language": case["language"], "patient_name": case["patient_name"],
            "source": case["source"],
            "mutations": [{k: m[k] for k in ("id", "kind", "layer", "targets")} for m in mod.MUTATIONS],
        }
    (HERE / "fixtures" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print("built", sum(len(v["mutations"]) + 2 for v in manifest.values()), "variants")


if __name__ == "__main__":
    main()
