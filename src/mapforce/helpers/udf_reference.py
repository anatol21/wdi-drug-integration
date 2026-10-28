"""Reference implementation of the MapForce helper UDFs (library wdi_helpers.mfd).

Every function below mirrors ONE MapForce user-defined function, step by step, using only the
operations available in MapForce's Built-in language (see ../README.md, section "UDF recipes"):

    MapForce core / lang function        Python equivalent used here
    -----------------------------------  ---------------------------------------------
    normalize-space(s)                   " ".join(s.split())
    lang:uppercase(s)                    s.upper()
    translate(s, ",", "")                s.replace(",", "")
    concat / substring-before / -after   _concat / _before / _after (XPath semantics)
    tokenize-regexp(s, p)                re.split(p, s)
    first-items / skip-first-items       slicing
    lookup in lookups/*.xml (filter)     _lookup()

It is the TEST ORACLE for the MapForce implementation: build the UDFs, run them on
udf_test_cases.csv, and compare with the expected columns. `python udf_reference.py` re-checks
the test cases and prints coverage statistics on the real FDA and DPD data.
"""
import csv
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOKUPS = HERE.parent / "lookups"


# ---------------------------------------------------------------- XPath-like primitives
def _before(s, d):
    """XPath substring-before: '' if d not in s."""
    i = s.find(d)
    return s[:i] if i >= 0 else ""


def _after(s, d):
    """XPath substring-after: '' if d not in s (and s itself if d == '')."""
    i = s.find(d)
    return s[i + len(d):] if i >= 0 else ""


def _normalize_space(s):
    return " ".join(s.split())


# ---------------------------------------------------------------- generic string UDFs
def clean_text(s):
    """UDF cleanText(s) = lang:uppercase(normalize-space(s))"""
    return _normalize_space(s or "").upper()


def before_or_self(s, delim):
    """UDF beforeOrSelf(s, delim) = substring-before(concat(s, delim), delim)"""
    return _before(s + delim, delim)


def first_word(s):
    """UDF firstWord(s) = beforeOrSelf(normalize-space(s), ' ')"""
    return before_or_self(_normalize_space(s), " ")


NUMBER_RE = re.compile(r"[0-9]*\.?[0-9]+")


def first_number(s):
    """UDF firstNumber(s): first number in s, or nothing.

    tokens = tokenize-regexp(concat("0 ", s), "[^0-9.]+")   -> "0", n1, n2, ...
    cand   = first-items(skip-first-items(tokens, 1), 1)      -> n1 (or nothing)
    result = cand if lang:match-pattern(cand, "[0-9]*\\.?[0-9]+") else nothing

    The "0 " prefix guarantees the first token is "0", so the result does not depend on whether
    tokenize-regexp keeps or drops a leading empty token.
    """
    tokens = re.split(r"[^0-9.]+", "0 " + s)
    cand = tokens[1] if len(tokens) > 1 else None
    if cand is None or not NUMBER_RE.fullmatch(cand):
        return None
    return cand


# ---------------------------------------------------------------- lookup UDFs
@lru_cache(maxsize=None)
def _table(filename):
    root = ET.parse(LOOKUPS / filename).getroot()
    return {e.get("raw"): e.attrib for e in root.iter("entry")}


def _lookup(filename, raw, attr="std"):
    """Generic lookup UDF:  key = cleanText(raw)
         found, std != ""  -> std
         found, std == ""  -> nothing (value carries no information, element is omitted)
         not found         -> key itself (new value stays visible instead of being lost)
    """
    key = clean_text(raw)
    if not key:
        return None
    entry = _table(filename).get(key)
    if entry is None:
        return key
    return entry.get(attr) or None


def std_regulatory_status(raw):
    return _lookup("regulatory_status.xml", raw)


def std_product_class(raw):
    return _lookup("product_class.xml", raw)


def std_dosage_form(raw):
    return _lookup("dosage_form.xml", raw)


def std_route(raw):
    return _lookup("route.xml", raw)


def std_unit(raw):
    return _lookup("strength_unit.xml", raw)


def std_atc_code(raw):
    """UDF stdAtcCode(raw): standardizes single or semicolon-separated ATC/ATCvet codes.
    - Strips '*' (e.g. DPD 'L04AA40*' -> 'L04AA40')
    - Drops placeholders ('NOT YET ASSIGNED', 'UNASSIGN')
    - Fixes EMA typo 'VO4D' -> 'V04D'
    - Deduplicates, sorts, and joins multiple codes with '; '
    """
    parts = []
    for token in (raw or "").split(";"):
        c = clean_text(token).replace("*", "")
        if not c or c in ("NOT YET ASSIGNED", "UNASSIGN"):
            continue
        if c == "VO4D":
            c = "V04D"
        parts.append(c)
    distinct = sorted(set(parts))
    return "; ".join(distinct) or None


# ---------------------------------------------------------------- list helpers
def std_list(values, sep, std_fn):
    """UDFs dosageFormList / routeList (value list -> standardised '; '-joined string)

    1. tokenize(values, sep) -> std_fn on each token          (drops tokens that map to nothing)
    2. string-join(..., '; ') then tokenize again on ';'      (a lookup may return 'A; B')
    3. normalize-space each, distinct-values, sort ascending, string-join(..., '; ')
    """
    mapped = [std_fn(t) for t in (values or "").split(sep)]
    joined = "; ".join(m for m in mapped if m)
    parts = sorted({_normalize_space(p) for p in joined.split(";") if _normalize_space(p)})
    return "; ".join(parts) or None


def dosage_form_list(values, sep=";"):
    return std_list(values, sep, std_dosage_form)


def route_list(values, sep=";"):
    return std_list((values or "").replace(",", sep), sep, std_route)


def best_regulatory_status(values, sep=";"):
    """UDF bestRegulatoryStatus(list): most favourable status of a multi-valued status field.
    sortKey lookup per token ("1-Authorised", "4-Withdrawn", ...) -> min-string -> substring-after '-'.
    """
    keys = [_lookup("regulatory_status.xml", t, "sortKey") for t in (values or "").split(sep)]
    keys = [k for k in keys if k and "-" in k]
    return _after(min(keys), "-") if keys else None


# ---------------------------------------------------------------- FDA-specific
def fda_form_part(form):
    """UDF fdaFormPart(Form) = beforeOrSelf(Form, ';')   e.g. 'TABLET, EXTENDED RELEASE;ORAL'"""
    return before_or_self(form or "", ";")


def fda_route_part(form):
    """UDF fdaRoutePart(Form) = substring-after(Form, ';')  -> comma-separated route list"""
    return _after(form or "", ";")


# ---------------------------------------------------------------- strength UDFs
def strength_core(raw):
    """UDF strengthCore(raw): the relevant part of one strength token.
    s = translate(cleanText(raw), ',', '')        20,000 UNITS/ML -> 20000 UNITS/ML
    s = beforeOrSelf(s, '**')                     drop FDA '**Federal Register ...' notes
    s = beforeOrSelf(s, '(')                      drop '(EQ 2MG BASE/ML)' style restatements
    result = normalize-space(s)
    """
    s = clean_text(raw).replace(",", "")
    s = before_or_self(s, "**")
    s = before_or_self(s, "(")
    return _normalize_space(s)


MASS_UNITS = {
    "mg", "g", "mcg", "kg", "mEq", "U", "IU", "Ci", "mCi", "mcCi", "mmol", "mcmol", "ng",
    "MG", "GM", "MCG", "UG", "G", "KG", "MEQ", "UNITS", "UNIT", "IU", "MCI", "UCI", "MMOL", "MCMOL", "NG",
}


def _parts(raw):
    core = strength_core(raw)
    v = first_number(core)
    if v is None:
        return None
    rest = _normalize_space(_after(core, v))
    numerator = before_or_self(rest, "/")
    denominator = _after(rest, "/")
    q = first_number(denominator)
    den_unit = _after(denominator, q) if q is not None else denominator
    return v, numerator, q, den_unit


def strength_value(raw):
    """UDF strengthValue(raw) -> xs:decimal or nothing
    v = firstNumber(core);  q = firstNumber(substring-after(substring-after(core, v), '/'))
    result = if (exists(q) and q > 0 and not is_mass_combo) round-precision(v div q, 6) else v
    """
    p = _parts(raw)
    if p is None:
        return None
    v, numerator, q, den_unit = p
    value = Decimal(v)
    nu_word = first_word(numerator) if numerator else ""
    du_word = first_word(den_unit) if den_unit else ""
    nu = std_unit(nu_word) or ""
    du = std_unit(du_word) or ""
    is_mass_combo = (nu in MASS_UNITS and du in MASS_UNITS) or (nu_word in MASS_UNITS and du_word in MASS_UNITS)
    if q is not None and Decimal(q) > 0 and not is_mass_combo:
        value = round(value / Decimal(q), 6)
    value = value.normalize()
    return format(value, "f")


def strength_unit(raw):
    """UDF strengthUnit(raw) -> standardised unit or nothing
    nu = stdUnit(firstWord(numerator))            'MG BASE' -> MG -> mg
    du = stdUnit(firstWord(denominator unit))     '10ML' -> ML -> mL ; 'VIAL' -> vial
    result = nu (for single/mass combo) or concat(nu, '/', du) when du exists and is volume/time/dose
    """
    p = _parts(raw)
    if p is None:
        return None
    _, numerator, _, den_unit = p
    nu_word = first_word(numerator) if numerator else ""
    du_word = first_word(den_unit) if den_unit else ""
    nu = std_unit(nu_word) if nu_word else None
    if not nu:
        return None
    du = std_unit(du_word) if du_word else None
    is_mass_combo = (nu in MASS_UNITS and du in MASS_UNITS) or (nu_word in MASS_UNITS and du_word in MASS_UNITS)
    if is_mass_combo:
        return nu
    return f"{nu}/{du}" if du else nu


def strengths(values, sep=";"):
    """How the mappers use the two UDFs: tokenize the list, keep tokens with a value."""
    out = []
    for t in (values or "").split(sep):
        v = strength_value(t)
        if v is not None:
            out.append((v, strength_unit(t)))
    return out


# ---------------------------------------------------------------- self-test / coverage
FUNCS = {
    "strengthValue": strength_value, "strengthUnit": strength_unit,
    "dosageForm": std_dosage_form, "dosageFormList": dosage_form_list,
    "route": std_route, "routeList": route_list,
    "fdaFormPart": fda_form_part, "fdaRoutePart": fda_route_part,
    "regulatoryStatus": std_regulatory_status, "bestRegulatoryStatus": best_regulatory_status,
    "productClass": std_product_class, "stdUnit": std_unit, "atcCode": std_atc_code,
}


def run_test_cases(path=HERE / "udf_test_cases.csv"):
    failures = 0
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        got = FUNCS[r["udf"]](r["input"])
        got = "" if got is None else got
        if got != r["expected"]:
            failures += 1
            print(f"FAIL {r['udf']}({r['input']!r}) = {got!r}, expected {r['expected']!r}")
    print(f"{len(rows) - failures}/{len(rows)} test cases passed")
    return failures


def coverage():
    import pandas as pd
    repo = HERE.parents[2]
    fda = pd.read_csv(repo / "data/1_raw/01_us_drugs_at_fda/Products.txt", sep="\t", dtype=str,
                      encoding="latin-1", keep_default_na=False)
    dpd = pd.read_csv(repo / "data/2_processed/dpd_medicines.csv", dtype=str,
                      encoding="utf-8-sig", keep_default_na=False)
    for label, series in (("FDA", fda.Strength), ("DPD", dpd.strengths)):
        toks = [t for s in series for t in s.split(";") if t.strip()]
        vals = [(strength_value(t), strength_unit(t)) for t in toks]
        n_val = sum(v is not None for v, _ in vals)
        n_unit = sum(u is not None for _, u in vals)
        print(f"{label} strengths: {len(toks)} tokens, value parsed {n_val / len(toks):.2%}, "
              f"unit parsed {n_unit / len(toks):.2%}")
        bad = [t for t, (v, u) in zip(toks, vals) if v is None or u is None]
        if bad:
            from collections import Counter
            print("   most frequent unparsed:", Counter(bad).most_common(8))


if __name__ == "__main__":
    fails = run_test_cases()
    if "--no-coverage" not in sys.argv:
        coverage()
    sys.exit(1 if fails else 0)
