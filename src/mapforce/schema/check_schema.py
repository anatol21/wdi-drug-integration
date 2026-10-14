"""Validate the target schema samples and keep the XML / JSON samples in sync.

Usage (from the repo root):
    python src/mapforce/schema/check_schema.py              # validate both samples
    python src/mapforce/schema/check_schema.py --regen-json  # rebuild sample JSON from sample XML
    python src/mapforce/schema/check_schema.py path/to/fda_medicines.xml   # validate any MapForce output

The XML -> JSON conversion here defines the canonical correspondence between both formats:
list wrappers become arrays, xs:boolean / xs:decimal / xs:integer become JSON booleans / numbers.
"""
import json
import sys
from pathlib import Path

import jsonschema
from lxml import etree

HERE = Path(__file__).resolve().parent
XSD = HERE / "medicines.xsd"
JSON_SCHEMA = HERE / "medicines.schema.json"
SAMPLE_XML = HERE / "sample_medicines.xml"
SAMPLE_JSON = HERE / "sample_medicines.json"

LISTS = {"activeSubstances": "activeSubstance", "strengths": "strength"}
INTS = {"activeSubstanceCount"}
BOOLS = {"generic", "biosimilar", "orphanMedicine"}


def _num(text):
    f = float(text)
    return int(f) if f.is_integer() else f


def medicine_to_dict(el):
    rec = {}
    for child in el:
        if not isinstance(child.tag, str):  # skip comments
            continue
        tag = child.tag
        if tag in LISTS:
            items = [c for c in child if isinstance(c.tag, str)]
            if tag == "strengths":
                rec[tag] = [
                    {k: (_num(v) if k == "value" else v)
                     for k, v in ((s.tag, s.text) for s in it if isinstance(s.tag, str))}
                    for it in items
                ]
            else:
                rec[tag] = [i.text for i in items]
        elif tag in INTS:
            rec[tag] = int(child.text)
        elif tag in BOOLS:
            rec[tag] = child.text.strip() in ("true", "1")
        else:
            rec[tag] = child.text
    return rec


def xml_to_json(xml_path):
    root = etree.parse(str(xml_path)).getroot()
    return {"medicines": [medicine_to_dict(m) for m in root if isinstance(m.tag, str)]}


def validate_xml(xml_path):
    schema = etree.XMLSchema(etree.parse(str(XSD)))
    doc = etree.parse(str(xml_path))
    if not schema.validate(doc):
        for err in list(schema.error_log)[:20]:
            print(f"  line {err.line}: {err.message}")
        raise SystemExit(f"XSD validation FAILED: {xml_path}")
    n = sum(1 for m in doc.getroot() if isinstance(m.tag, str))
    print(f"XSD  OK  {xml_path.name} ({n} medicines)")


def validate_json(obj, label):
    schema = json.loads(JSON_SCHEMA.read_text())
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.path))
    if errors:
        for e in errors[:20]:
            print(f"  {list(e.path)}: {e.message}")
        raise SystemExit(f"JSON Schema validation FAILED: {label}")
    print(f"JSON OK  {label} ({len(obj['medicines'])} medicines)")


def main(argv):
    if "--regen-json" in argv:
        SAMPLE_JSON.write_text(json.dumps(xml_to_json(SAMPLE_XML), indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {SAMPLE_JSON.name}")
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if paths:
        for p in paths:
            if p.suffix == ".json":
                validate_json(json.loads(p.read_text()), p.name)
            else:
                validate_xml(p)
        return
    validate_xml(SAMPLE_XML)
    sample_json = json.loads(SAMPLE_JSON.read_text())
    validate_json(sample_json, SAMPLE_JSON.name)
    if sample_json != xml_to_json(SAMPLE_XML):
        raise SystemExit("sample_medicines.json is out of sync with the XML sample (run with --regen-json)")
    print("XML and JSON samples are equivalent")


if __name__ == "__main__":
    main(sys.argv[1:])
