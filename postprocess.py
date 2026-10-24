"""Постобработка OCR паспорта РФ: accept/reject + поля.

Запуск: python postprocess.py data/test_predictions.jsonl answers.jsonl

Только стандартная библиотека, CPU, без интернета.
"""
import json
import sys
from datetime import date

FIELDS = ["Last_name_ru", "First_name_ru", "Middle_name_ru", "Sex_ru", "Birth_date",
          "Birth_place_ru", "Issue_date", "Issue_organisation_code", "Licence_number",
          "Issue_organization_ru"]

DEADLINE = date(2026, 10, 1)
VALID_YEARS = 20
CONF_THRESHOLD = 0.99          # средняя уверенность поля (для ветки без MRZ)
CHAR_CONF_THRESHOLD = 0.95    # min(char_conf) по alnum-символам
WEIGHTS = (7, 3, 1)


def norm(s):
    return " ".join(str(s or "").split()).upper()


def norm_compact(s):
    return "".join(ch for ch in norm(s) if ch.isalnum())


def viz_text(v):
    if isinstance(v, dict):
        return " ".join((ln.get("text") or "") for ln in (v.get("lines") or []))
    return v or ""


def viz_conf(v):
    if isinstance(v, dict) and isinstance(v.get("conf"), (int, float)):
        return float(v["conf"])
    return 0.0


def min_char_conf(v):
    """min(char_conf) только по буквам/цифрам (пробелы и пунктуация игнорируются)."""
    if not isinstance(v, dict):
        return None
    vals = []
    for ln in (v.get("lines") or []):
        text = ln.get("text") or ""
        confs = ln.get("char_conf") or []
        for ch, c in zip(text, confs):
            if not isinstance(c, (int, float)):
                continue
            if ch.isalnum():
                vals.append(float(c))
    return min(vals) if vals else None


def check_digit(s):
    total = 0
    for i, ch in enumerate(s):
        val = 0 if ch == "<" else (int(ch) if ch.isdigit() else 0)
        total += WEIGHTS[i % 3] * val
    return total % 10


def yymmdd_to_date(s):
    if len(s) != 6 or not s.isdigit():
        return None
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    for year in (2000 + yy, 1900 + yy):
        try:
            d = date(year, mm, dd)
        except ValueError:
            continue
        if d <= DEADLINE:
            return d
    return None


def parse_ddmmyyyy(s):
    s = norm(s)
    if len(s) != 10 or s[2] != "." or s[5] != ".":
        return None
    try:
        return date(int(s[6:10]), int(s[3:5]), int(s[0:2]))
    except ValueError:
        return None


def fmt_date(d):
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"


def is_valid_passport(issue_str):
    d = parse_ddmmyyyy(issue_str)
    if d is None:
        return False
    try:
        expiry = date(d.year + VALID_YEARS, d.month, d.day)
    except ValueError:
        expiry = date(d.year + VALID_YEARS, d.month, 28)
    return expiry >= DEADLINE


def parse_mrz(mrz):
    lines = (mrz or {}).get("lines") or []
    if len(lines) != 2:
        return None
    s0 = lines[0].get("text") or ""
    s1 = lines[1].get("text") or ""
    if len(s0) != 44 or len(s1) != 44:
        return None
    if not s0.startswith("PNRUS"):
        return None
    if s1[9] != str(check_digit(s1[0:9])):
        return None
    if s1[19] != str(check_digit(s1[13:19])):
        return None
    if s1[20] not in ("M", "F"):
        return None
    birth = yymmdd_to_date(s1[13:19])
    issue = yymmdd_to_date(s1[29:35])
    if birth is None or issue is None:
        return None
    code6 = s1[35:41]
    if not code6.isdigit():
        return None
    return {
        "lic_head": s1[0:3],
        "lic_tail": s1[3:9],
        "Birth_date": fmt_date(birth),
        "Sex_ru": "МУЖ." if s1[20] == "M" else "ЖЕН.",
        "Issue_date": fmt_date(issue),
        "Issue_organisation_code": f"{code6[0:3]}-{code6[3:6]}",
    }


def licence_matches(vz_lic, mrz):
    s = norm_compact(vz_lic)
    if len(s) != 10:
        return False
    return s[0:3] == mrz["lic_head"] and s[4:10] == mrz["lic_tail"]


def check_all_char_conf(viz):
    """min(char_conf) >= CHAR_CONF_THRESHOLD (0.95) для всех VZ-полей (кроме пустого отчества)."""
    for f in ("Last_name_ru", "First_name_ru", "Middle_name_ru",
              "Birth_place_ru", "Issue_organization_ru"):
        v = viz.get(f)
        if f == "Middle_name_ru" and not viz_text(v):
            continue
        mc = min_char_conf(v)
        if mc is not None and mc < CHAR_CONF_THRESHOLD:
            return f
    return None


def decide(doc):
    viz = doc.get("viz") or {}
    vz = {f: viz_text(viz.get(f)) for f in FIELDS}
    confs = {f: viz_conf(viz.get(f)) for f in FIELDS}
    mrz = parse_mrz(doc.get("mrz"))

    # 1. Просрочен на 01.10.2026 (по MRZ, если есть, иначе по VZ)
    issue_for_check = mrz["Issue_date"] if mrz else vz["Issue_date"]
    if not is_valid_passport(issue_for_check):
        return "reject", None, "expired"

    # 2. Есть валидный MRZ — он подтверждает даты/пол/код/номер
    if mrz is not None:
        if norm(vz["Birth_date"]) != norm(mrz["Birth_date"]):
            return "reject", None, "mrz_birth"
        if norm(vz["Sex_ru"]) != norm(mrz["Sex_ru"]):
            return "reject", None, "mrz_sex"
        if norm(vz["Issue_date"]) != norm(mrz["Issue_date"]):
            return "reject", None, "mrz_issue"
        if norm_compact(vz["Issue_organisation_code"]) != norm_compact(mrz["Issue_organisation_code"]):
            return "reject", None, "mrz_code"
        if not licence_matches(vz["Licence_number"], mrz):
            return "reject", None, "mrz_licence"
        for f in FIELDS:
            if f == "Middle_name_ru":
                continue
            if not vz[f]:
                return "reject", None, "empty_" + f
        bad = check_all_char_conf(viz)
        if bad:
            return "reject", None, "low_char_conf_" + bad
        out = dict(vz)
        out["Birth_date"] = mrz["Birth_date"]
        out["Sex_ru"] = mrz["Sex_ru"]
        out["Issue_date"] = mrz["Issue_date"]
        out["Issue_organisation_code"] = mrz["Issue_organisation_code"]
        s = norm_compact(vz["Licence_number"])
        if len(s) == 10:
            out["Licence_number"] = f"{s[0:2]} {s[2:4]} {s[4:10]}"
        return "accept", out, "mrz_ok"

    # 3. Без MRZ — строго: conf + char_conf
    for f in FIELDS:
        if f == "Middle_name_ru":
            continue
        if not vz[f]:
            return "reject", None, "nomrz_empty_" + f
        if confs[f] < CONF_THRESHOLD:
            return "reject", None, "nomrz_conf_" + f
    if not is_valid_passport(vz["Issue_date"]):
        return "reject", None, "nomrz_expired"
    bad = check_all_char_conf(viz)
    if bad:
        return "reject", None, "nomrz_low_char_conf_" + bad
    return "accept", vz, "nomrz_ok"


def main(pred_path, out_path):
    stats = {}
    with open(pred_path, encoding="utf-8") as fh, open(out_path, "w", encoding="utf-8") as out:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            decision, fields, reason = decide(doc)
            stats[reason] = stats.get(reason, 0) + 1
            rec = {"doc_id": doc["doc_id"], "decision": decision}
            if decision == "accept":
                rec["fields"] = {f: fields[f] for f in FIELDS}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    total = sum(stats.values())
    acc = sum(v for k, v in stats.items() if k.endswith("_ok"))
    print(f"всего {total}, accept {acc} ({acc/total:.1%}), reject {total-acc}", file=sys.stderr)
    for r, c in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {r}: {c}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python postprocess.py <predictions.jsonl> <answers.jsonl>")
    main(sys.argv[1], sys.argv[2])