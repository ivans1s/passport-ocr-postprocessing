"""Полная метрика на train (с проверкой действительности на 01.10.2026).

Запуск: python score.py answers_train.jsonl data/train_labels.jsonl
"""
import json
import sys
from datetime import date

FIELDS = ["Last_name_ru", "First_name_ru", "Middle_name_ru", "Sex_ru", "Birth_date",
          "Birth_place_ru", "Issue_date", "Issue_organisation_code", "Licence_number",
          "Issue_organization_ru"]
DEADLINE = date(2026, 10, 1)
VALID_YEARS = 20


def norm(s):
    return " ".join(str(s or "").split()).upper()


def load(path):
    return {d["doc_id"]: d for d in map(json.loads, open(path, encoding="utf-8"))}


def is_valid(issue_str):
    s = norm(issue_str)
    if len(s) != 10:
        return False
    try:
        d = date(int(s[6:10]), int(s[3:5]), int(s[0:2]))
    except ValueError:
        return False
    try:
        exp = date(d.year + VALID_YEARS, d.month, d.day)
    except ValueError:
        exp = date(d.year + VALID_YEARS, d.month, 28)
    return exp >= DEADLINE


def main(ans_path, gt_path):
    ans = load(ans_path)
    gt = load(gt_path)
    n = len(gt)
    good = bad = rejected = rejected_valid = 0
    field_err = {f: 0 for f in FIELDS}
    for doc_id, g in gt.items():
        gf = g["fields"]
        a = ans.get(doc_id) or {}
        if a.get("decision") != "accept":
            rejected += 1
            if is_valid(gf["Issue_date"]):
                rejected_valid += 1
            continue
        af = a.get("fields") or {}
        wrong = [f for f in FIELDS if norm(af.get(f)) != norm(gf[f])]
        for f in wrong:
            field_err[f] += 1
        if not wrong and is_valid(gf["Issue_date"]):
            good += 1
        else:
            bad += 1
    accepted = good + bad
    precision = good / accepted if accepted else 0.0
    recall = good / n if n else 0.0
    print(f"документов:              {n}")
    print(f"принято всего:           {accepted} ({accepted/n:.1%})")
    print(f"  принято верно:         {good} ({good/n:.1%})")
    print(f"  принято с ошибкой:     {bad}")
    print(f"  precision:             {precision:.2%}")
    print(f"  recall:                {recall:.2%}")
    print(f"отклонено:               {rejected} ({rejected/n:.1%})")
    print(f"  из них были валидны:   {rejected_valid}")
    print("ошибки по полям (среди принятых):")
    for f, c in field_err.items():
        if c:
            print(f"  {f}: {c}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])