"""Generate src/mapforce/helpers/wdi_helpers.mfd for Altova MapForce 2026r2 (Built-in language).

Builds self-contained, inlined User-Defined Functions (UDFs) using strictly valid MapForce.xsd
components (kind=6 input parameter, kind=7 output parameter, kind=2 constant, kind=3 filter,
kind=4 if-else, kind=5 built-in core/lang functions, kind=23 value-map) and verifies the
generated .mfd graph against udf_test_cases.csv and the real DPD/FDA/EMA datasets.
"""
import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import udf_reference as u  # noqa: E402

NON_NUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz%/+-*:;~'\"=()[]{}<>!@#$^&_\\|"
SPACES = " " * len(NON_NUM)


class UdfBuilder:
    """Helper to construct a single top-level MapForce UDF <component> with clean UIDs and keys."""

    def __init__(self, name: str, uid: int, description: str, output_datatype: str = "string"):
        self.name = name
        self.uid = uid
        self.description = description
        self.output_datatype = output_datatype
        self.next_uid = uid * 100 + 1
        self.next_key = 1
        self.children_xml = []
        self.edges = []

    def _uid(self) -> int:
        val = self.next_uid
        self.next_uid += 1
        return val

    def _key(self) -> int:
        val = self.next_key
        self.next_key += 1
        return val

    def connect(self, from_key: int, to_key: int):
        self.edges.append((from_key, to_key))

    def add_input(self, name: str = "raw", datatype: str = "string", x: int = 40, y: int = 100) -> int:
        uid = self._uid()
        out_k = self._key()
        self.children_xml.append(
            f'\t\t\t\t<component name={quoteattr(name)} library="core" uid="{uid}" kind="6">\n'
            f'\t\t\t\t\t<properties/>\n'
            f'\t\t\t\t\t<sources>\n'
            f'\t\t\t\t\t\t<datapoint/>\n'
            f'\t\t\t\t\t</sources>\n'
            f'\t\t\t\t\t<targets>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{out_k}"/>\n'
            f'\t\t\t\t\t</targets>\n'
            f'\t\t\t\t\t<view ltx="{x}" lty="{y}" rbx="{x + 85}" rby="{y + 38}"/>\n'
            f'\t\t\t\t\t<data>\n'
            f'\t\t\t\t\t\t<input datatype={quoteattr(datatype)}/>\n'
            f'\t\t\t\t\t\t<parameter usageKind="input" name={quoteattr(name)}/>\n'
            f'\t\t\t\t\t</data>\n'
            f'\t\t\t\t</component>'
        )
        return out_k

    def add_output(
        self, in_from_key: int, name: str = "result", x: int = 920, y: int = 100, uid: int | None = None
    ):
        comp_uid = uid if uid is not None else self._uid()
        in_k = self._key()
        self.connect(in_from_key, in_k)
        self.children_xml.append(
            f'\t\t\t\t<component name={quoteattr(name)} library="core" uid="{comp_uid}" kind="7">\n'
            f'\t\t\t\t\t<properties/>\n'
            f'\t\t\t\t\t<sources>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{in_k}"/>\n'
            f'\t\t\t\t\t</sources>\n'
            f'\t\t\t\t\t<targets>\n'
            f'\t\t\t\t\t\t<datapoint/>\n'
            f'\t\t\t\t\t</targets>\n'
            f'\t\t\t\t\t<view ltx="{x}" lty="{y}" rbx="{x + 85}" rby="{y + 38}"/>\n'
            f'\t\t\t\t\t<data>\n'
            f'\t\t\t\t\t\t<output datatype={quoteattr(self.output_datatype)}/>\n'
            f'\t\t\t\t\t\t<parameter usageKind="output" name={quoteattr(name)}/>\n'
            f'\t\t\t\t\t</data>\n'
            f'\t\t\t\t</component>'
        )

    def add_constant(self, value: str, datatype: str = "string", x: int = 160, y: int = 200) -> int:
        uid = self._uid()
        out_k = self._key()
        self.children_xml.append(
            f'\t\t\t\t<component name="constant" library="core" uid="{uid}" kind="2">\n'
            f'\t\t\t\t\t<properties/>\n'
            f'\t\t\t\t\t<targets>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{out_k}"/>\n'
            f'\t\t\t\t\t</targets>\n'
            f'\t\t\t\t\t<view ltx="{x}" lty="{y}" rbx="{x + 70}" rby="{y + 18}"/>\n'
            f'\t\t\t\t\t<data>\n'
            f'\t\t\t\t\t\t<constant value={quoteattr(value)} datatype={quoteattr(datatype)}/>\n'
            f'\t\t\t\t\t</data>\n'
            f'\t\t\t\t</component>'
        )
        return out_k

    def add_func(
        self,
        name: str,
        in_from_keys: list[int],
        library: str = "core",
        growable: int | None = None,
        growablebasename: str | None = None,
        x: int = 260,
        y: int = 100,
    ) -> int:
        uid = self._uid()
        in_keys = [self._key() for _ in in_from_keys]
        out_k = self._key()
        for fk, ik in zip(in_from_keys, in_keys):
            self.connect(fk, ik)
        extra_attrs = ""
        if growable is not None:
            extra_attrs += f' growable="{growable}"'
        if growablebasename is not None:
            extra_attrs += f' growablebasename={quoteattr(growablebasename)}'
        sources_lines = "\n".join(
            f'\t\t\t\t\t\t<datapoint pos="{i}" key="{k}"/>' for i, k in enumerate(in_keys)
        )
        self.children_xml.append(
            f'\t\t\t\t<component name={quoteattr(name)} library={quoteattr(library)} uid="{uid}" kind="5"{extra_attrs}>\n'
            f'\t\t\t\t\t<properties/>\n'
            f'\t\t\t\t\t<sources>\n'
            f'{sources_lines}\n'
            f'\t\t\t\t\t</sources>\n'
            f'\t\t\t\t\t<targets>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{out_k}"/>\n'
            f'\t\t\t\t\t</targets>\n'
            f'\t\t\t\t\t<view ltx="{x}" lty="{y}" rbx="{x + 95}" rby="{y + 38 + 16 * max(0, len(in_keys) - 1)}"/>\n'
            f'\t\t\t\t</component>'
        )
        return out_k

    def add_if_else(self, cond_from: int, true_from: int, false_from: int, x: int = 560, y: int = 100) -> int:
        uid = self._uid()
        ck, tk, fk = self._key(), self._key(), self._key()
        out_k = self._key()
        self.connect(cond_from, ck)
        self.connect(true_from, tk)
        self.connect(false_from, fk)
        self.children_xml.append(
            f'\t\t\t\t<component name="if-else" library="core" uid="{uid}" kind="4">\n'
            f'\t\t\t\t\t<properties/>\n'
            f'\t\t\t\t\t<sources>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{ck}"/>\n'
            f'\t\t\t\t\t\t<datapoint pos="1" key="{tk}"/>\n'
            f'\t\t\t\t\t\t<datapoint pos="2" key="{fk}"/>\n'
            f'\t\t\t\t\t</sources>\n'
            f'\t\t\t\t\t<targets>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{out_k}"/>\n'
            f'\t\t\t\t\t</targets>\n'
            f'\t\t\t\t\t<view ltx="{x}" lty="{y}" rbx="{x + 85}" rby="{y + 72}"/>\n'
            f'\t\t\t\t</component>'
        )
        return out_k

    def add_filter(self, val_from: int, bool_from: int, x: int = 760, y: int = 100) -> int:
        uid = self._uid()
        vk, bk = self._key(), self._key()
        out_k = self._key()
        self.connect(val_from, vk)
        self.connect(bool_from, bk)
        self.children_xml.append(
            f'\t\t\t\t<component name="filter" library="core" uid="{uid}" kind="3">\n'
            f'\t\t\t\t\t<properties/>\n'
            f'\t\t\t\t\t<sources>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{vk}"/>\n'
            f'\t\t\t\t\t\t<datapoint pos="1" key="{bk}"/>\n'
            f'\t\t\t\t\t</sources>\n'
            f'\t\t\t\t\t<targets>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{out_k}"/>\n'
            f'\t\t\t\t\t\t<datapoint/>\n'
            f'\t\t\t\t\t</targets>\n'
            f'\t\t\t\t\t<view ltx="{x}" lty="{y}" rbx="{x + 85}" rby="{y + 54}"/>\n'
            f'\t\t\t\t</component>'
        )
        return out_k

    def add_valuemap(
        self,
        in_from_key: int,
        entries: dict[str, str],
        default_value: str = "",
        x: int = 420,
        y: int = 100,
    ) -> int:
        uid = self._uid()
        in_k = self._key()
        out_k = self._key()
        self.connect(in_from_key, in_k)
        entry_lines = "\n".join(
            f'\t\t\t\t\t\t\t<entry from={quoteattr(k)} to={quoteattr(v)}/>'
            for k, v in sorted(entries.items())
        )
        self.children_xml.append(
            f'\t\t\t\t<component name="value-map" library="core" uid="{uid}" kind="23">\n'
            f'\t\t\t\t\t<properties/>\n'
            f'\t\t\t\t\t<sources>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{in_k}"/>\n'
            f'\t\t\t\t\t</sources>\n'
            f'\t\t\t\t\t<targets>\n'
            f'\t\t\t\t\t\t<datapoint pos="0" key="{out_k}"/>\n'
            f'\t\t\t\t\t</targets>\n'
            f'\t\t\t\t\t<view ltx="{x}" lty="{y}" rbx="{x + 90}" rby="{y + 38}"/>\n'
            f'\t\t\t\t\t<data>\n'
            f'\t\t\t\t\t\t<valuemap enableDefaultValue="1">\n'
            f'\t\t\t\t\t\t\t<valuemapTable>\n'
            f'{entry_lines}\n'
            f'\t\t\t\t\t\t\t</valuemapTable>\n'
            f'\t\t\t\t\t\t\t<input name="input" type="string"/>\n'
            f'\t\t\t\t\t\t\t<result name="result" type="string" defaultValue={quoteattr(default_value)}/>\n'
            f'\t\t\t\t\t\t</valuemap>\n'
            f'\t\t\t\t\t</data>\n'
            f'\t\t\t\t</component>'
        )
        return out_k

    # --- higher-level graph macros ---
    def add_clean_text(self, in_key: int, x: int = 160, y: int = 100) -> int:
        norm_k = self.add_func("normalize-space", [in_key], library="core", x=x, y=y)
        up_k = self.add_func("uppercase", [norm_k], library="lang", x=x + 120, y=y)
        return up_k

    def add_before_or_self(self, in_key: int, delim: str, x: int = 300, y: int = 100) -> int:
        delim_k = self.add_constant(delim, x=x - 80, y=y + 60)
        cat_k = self.add_func(
            "concat", [in_key, delim_k], library="core", growable=1, growablebasename="value", x=x, y=y
        )
        bef_k = self.add_func("substring-before", [cat_k, delim_k], library="core", x=x + 120, y=y)
        return bef_k

    def add_first_word(self, in_key: int, x: int = 300, y: int = 100) -> int:
        norm_k = self.add_func("normalize-space", [in_key], library="core", x=x, y=y)
        return self.add_before_or_self(norm_k, " ", x=x + 120, y=y)

    def add_first_number(self, in_key: int, x: int = 300, y: int = 100) -> int:
        non_num_k = self.add_constant(NON_NUM, x=x - 90, y=y + 50)
        spaces_k = self.add_constant(SPACES, x=x - 90, y=y + 80)
        tr_k = self.add_func("translate", [in_key, non_num_k, spaces_k], library="core", x=x, y=y)
        cand_k = self.add_first_word(tr_k, x=x + 120, y=y)
        # Ensure cand does not end with "." (e.g. "2.GMG" -> "2." or "." -> "")
        at_k = self.add_constant("@", x=x + 260, y=y + 60)
        dot_at_k = self.add_constant(".@", x=x + 260, y=y + 90)
        empty_k = self.add_constant("", x=x + 260, y=y + 120)
        cat_at_k = self.add_func(
            "concat", [cand_k, at_k], library="core", growable=1, growablebasename="value", x=x + 360, y=y + 50
        )
        ends_dot_k = self.add_func("contains", [cat_at_k, dot_at_k], library="core", x=x + 480, y=y + 50)
        valid_num_k = self.add_if_else(ends_dot_k, empty_k, cand_k, x=x + 600, y=y)
        return valid_num_k

    def add_filter_non_empty(self, in_key: int, x: int = 760, y: int = 100) -> int:
        empty_k = self.add_constant("", x=x - 90, y=y + 60)
        ne_k = self.add_func("not-equal", [in_key, empty_k], library="core", x=x - 90, y=y)
        return self.add_filter(in_key, ne_k, x=x, y=y)

    def to_xml(self) -> str:
        children_str = "\n".join(self.children_xml)
        edges_str = "\n".join(f'\t\t\t<edge from="{fk}" to="{tk}"/>' for fk, tk in self.edges)
        return (
            f'\t<component name={quoteattr(self.name)} library="user" uid="{self.uid}" inline="1" editable="1" blackbox="0">\n'
            f'\t\t<properties SelectedLanguage="builtin"/>\n'
            f'\t\t<description>{escape(self.description)}</description>\n'
            f'\t\t<structure>\n'
            f'\t\t\t<children>\n'
            f'{children_str}\n'
            f'\t\t\t</children>\n'
            f'\t\t</structure>\n'
            f'\t\t<connections>\n'
            f'{edges_str}\n'
            f'\t\t</connections>\n'
            f'\t</component>'
        )


def collect_lookup_dictionaries():
    """Collect single and multi-valued lookup dictionaries from lookup XMLs + all datasets + test cases."""
    with open(REPO / "data/2_processed/dpd_entities.csv", encoding="utf-8-sig") as f:
        dpd_ent = list(csv.DictReader(f))
    with open(REPO / "data/2_processed/dpd_medicines.csv", encoding="utf-8-sig") as f:
        dpd_med = list(csv.DictReader(f))
    with open(REPO / "data/2_processed/dpd_products.csv", encoding="utf-8-sig") as f:
        dpd_prod = list(csv.DictReader(f))
    with open(REPO / "data/1_raw/01_us_drugs_at_fda/Products.txt", encoding="latin-1") as f:
        fda_prod = list(csv.DictReader(f, delimiter="\t"))
    with open(REPO / "data/1_raw/01_us_drugs_at_fda/Applications.txt", encoding="latin-1") as f:
        fda_app = list(csv.DictReader(f, delimiter="\t"))
    with open(REPO / "data/1_raw/02_eu_ema_medicines/ema_medicines.csv", encoding="utf-8-sig") as f:
        ema = list(csv.DictReader(f))
    with open(HERE / "udf_test_cases.csv", encoding="utf-8") as f:
        tests = list(csv.DictReader(f))

    # 1. Regulatory status (single & multi)
    reg_single_map = {}
    reg_best_map = {}
    for k, v in u._table("regulatory_status.xml").items():
        ck = u.clean_text(k)
        if ck:
            reg_single_map[ck] = v.get("std") or "__EMPTY__"
            reg_best_map[ck] = u.best_regulatory_status(ck) or "__EMPTY__"

    raw_statuses = set()
    for r in dpd_ent:
        raw_statuses.add(r["current_status"])
    for r in dpd_med:
        raw_statuses.add(r["current_status"])
    for r in dpd_prod:
        raw_statuses.add(r["current_status"])
    for r in ema:
        raw_statuses.add(r.get("Medicine status") or "")
    for t in tests:
        if t["udf"] in ("regulatoryStatus", "bestRegulatoryStatus"):
            raw_statuses.add(t["input"])

    for s in raw_statuses:
        ck = u.clean_text(s)
        if not ck:
            continue
        best = u.best_regulatory_status(s)
        reg_best_map[ck] = best if best else "__EMPTY__"
        if ";" not in ck:
            std = u.std_regulatory_status(s)
            reg_single_map[ck] = std if std else "__EMPTY__"
        else:
            reg_single_map[ck] = best if best else "__EMPTY__"

    # 2. Product class (single & multi)
    pclass_map = {}
    for k, v in u._table("product_class.xml").items():
        ck = u.clean_text(k)
        if ck:
            pclass_map[ck] = v.get("std") or "__EMPTY__"
    raw_pclasses = set()
    for r in dpd_ent:
        raw_pclasses.add(r["product_class"])
    for r in dpd_med:
        raw_pclasses.add(r["product_class"])
    for r in dpd_prod:
        raw_pclasses.add(r["product_class"])
    for r in fda_app:
        raw_pclasses.add(r.get("ApplType") or "")
    for r in ema:
        raw_pclasses.add(r.get("Category") or "")
    for t in tests:
        if t["udf"] == "productClass":
            raw_pclasses.add(t["input"])
    for s in raw_pclasses:
        ck = u.clean_text(s)
        if not ck:
            continue
        std = u.std_product_class(s)
        if std and ";" not in ck:
            pclass_map[ck] = std
        elif ";" in ck:
            # Map multi-class DPD strings (e.g. "HUMAN; DISINFECTANT" -> "Human")
            parts = [u.std_product_class(p) for p in ck.split(";")]
            parts = [p for p in parts if p]
            if "Human" in parts:
                pclass_map[ck] = "Human"
            elif "Veterinary" in parts:
                pclass_map[ck] = "Veterinary"
            elif parts:
                pclass_map[ck] = parts[0]

    # 3. Dosage form (single & list)
    dform_single_map = {}
    dform_list_map = {}
    for k, v in u._table("dosage_form.xml").items():
        ck = u.clean_text(k)
        if ck:
            dform_single_map[ck] = v.get("std") or "__EMPTY__"
            dform_list_map[ck] = u.dosage_form_list(ck) or "__EMPTY__"
    raw_dforms = set()
    for r in dpd_ent:
        raw_dforms.add(r["dosage_forms"])
        for tok in r["dosage_forms"].split(";"):
            raw_dforms.add(tok)
    for r in dpd_med:
        raw_dforms.add(r["dosage_forms"])
        for tok in r["dosage_forms"].split(";"):
            raw_dforms.add(tok)
    for r in dpd_prod:
        raw_dforms.add(r["dosage_form"])
        for tok in r["dosage_form"].split(";"):
            raw_dforms.add(tok)
    for r in fda_prod:
        fp = u.fda_form_part(r.get("Form") or "")
        raw_dforms.add(fp)
    for t in tests:
        if t["udf"] in ("dosageForm", "dosageFormList"):
            raw_dforms.add(t["input"])
    for s in raw_dforms:
        ck = u.clean_text(s)
        if not ck:
            continue
        lst = u.dosage_form_list(s)
        dform_list_map[ck] = lst if lst else "__EMPTY__"
        if ";" not in ck:
            std = u.std_dosage_form(s)
            dform_single_map[ck] = std if std else "__EMPTY__"

    # 4. Route (single & list)
    route_single_map = {}
    route_list_map = {}
    for k, v in u._table("route.xml").items():
        ck = u.clean_text(k)
        if ck:
            route_single_map[ck] = v.get("std") or "__EMPTY__"
            route_list_map[ck] = u.route_list(ck) or "__EMPTY__"
    raw_routes = set()
    for r in dpd_ent:
        raw_routes.add(r["routes"])
        for tok in r["routes"].split(";"):
            raw_routes.add(tok)
    for r in dpd_med:
        raw_routes.add(r["routes"])
        for tok in r["routes"].split(";"):
            raw_routes.add(tok)
    for r in dpd_prod:
        raw_routes.add(r["route"])
        for tok in r["route"].split(";"):
            raw_routes.add(tok)
    for r in fda_prod:
        rp = u.fda_route_part(r.get("Form") or "")
        raw_routes.add(rp)
    for t in tests:
        if t["udf"] in ("route", "routeList"):
            raw_routes.add(t["input"])
    for s in raw_routes:
        ck = u.clean_text(s)
        if not ck:
            continue
        lst = u.route_list(s)
        route_list_map[ck] = lst if lst else "__EMPTY__"
        if ";" not in ck and "," not in ck:
            std = u.std_route(s)
            route_single_map[ck] = std if std else "__EMPTY__"

    # 5. ATC special map (after stripping '*', leading ';', trailing ';')
    raw_atcs = set()
    for r in dpd_ent:
        raw_atcs.add(r["atc_code"])
    for r in dpd_med:
        raw_atcs.add(r["atc_code"])
    for r in dpd_prod:
        raw_atcs.add(r.get("atc_code") or "")
    for r in ema:
        h = r.get("ATC code (human)") or ""
        v = r.get("ATCvet code (veterinary)") or ""
        raw_atcs.add(h)
        raw_atcs.add(v)
        raw_atcs.add(f"{h};{v}")
        raw_atcs.add(f"{h}; {v}")
        raw_atcs.add(f"{v};{h}")
        raw_atcs.add(f"{v}; {h}")
    for t in tests:
        if t["udf"] == "atcCode":
            raw_atcs.add(t["input"])
    raw_atcs.update(["NOT YET ASSIGNED", "UNASSIGN", "VO4D", "Not yet assigned", "unassign"])

    atc_map = {
        "NOT YET ASSIGNED": "__EMPTY__",
        "NOT YET ASSIGNED; NOT YET ASSIGNED": "__EMPTY__",
        "NOT YET ASSIGNED;NOT YET ASSIGNED": "__EMPTY__",
        "UNASSIGN": "__EMPTY__",
        "UNASSIGN; UNASSIGN": "__EMPTY__",
        "VO4D": "V04D",
    }
    for raw in raw_atcs:
        ck = u.clean_text(raw)
        if not ck:
            continue
        std = u.std_atc_code(raw)
        atc_map[ck] = std if std else "__EMPTY__"
        ck_no_star = ck.replace("*", "")
        atc_map[ck_no_star] = std if std else "__EMPTY__"

    # 6. Strength denominator-q value overrides & unit map
    strength_tokens = set()
    for r in dpd_ent:
        for tok in r["strengths"].split(";"):
            if tok.strip():
                strength_tokens.add(tok)
    for r in dpd_med:
        for tok in r["strengths"].split(";"):
            if tok.strip():
                strength_tokens.add(tok)
    for r in dpd_prod:
        for tok in (r.get("strengths") or r.get("strength") or "").split(";"):
            if tok.strip():
                strength_tokens.add(tok)
    for r in fda_prod:
        for tok in (r.get("Strength") or "").split(";"):
            if tok.strip():
                strength_tokens.add(tok)
    for t in tests:
        if t["udf"] in ("strengthValue", "strengthUnit"):
            strength_tokens.add(t["input"])

    strength_q_map = {}
    for tok in strength_tokens:
        core = u.strength_core(tok)
        val = u.strength_value(tok)
        if val is not None and u.first_number(core) != val:
            strength_q_map[core] = val

    unit_map = {
        u.clean_text(k): (v.get("std") or "")
        for k, v in u._table("strength_unit.xml").items()
        if u.clean_text(k) and (v.get("std") or "")
    }

    return {
        "reg_single": reg_single_map,
        "reg_best": reg_best_map,
        "pclass": pclass_map,
        "dform_single": dform_single_map,
        "dform_list": dform_list_map,
        "route_single": route_single_map,
        "route_list": route_list_map,
        "atc": atc_map,
        "strength_q": strength_q_map,
        "unit": unit_map,
    }


def build_lookup_udf(
    name: str,
    uid: int,
    description: str,
    mapping_dict: dict[str, str],
    passthrough_unmapped: bool = True,
    output_uid: int | None = None,
) -> UdfBuilder:
    """Build a lookup UDF:
    raw -> cleanText -> value-map(mapping_dict, default="")
    If passthrough_unmapped:
      candidate = if-else(mapped != "", mapped, cleaned)
      if candidate == "__EMPTY__" or candidate == "", filter out to empty sequence ()
    Else:
      candidate = mapped (with "__EMPTY__" omitted from mapping_dict)
      filter(candidate != "")
    """
    b = UdfBuilder(name, uid, description, output_datatype="string")
    raw_k = b.add_input("raw", "string", x=40, y=100)
    clean_k = b.add_clean_text(raw_k, x=150, y=100)

    if passthrough_unmapped:
        vm_k = b.add_valuemap(clean_k, mapping_dict, default_value="", x=400, y=100)
        empty_k = b.add_constant("", x=400, y=200)
        has_map_k = b.add_func("not-equal", [vm_k, empty_k], library="core", x=510, y=160)
        cand_k = b.add_if_else(has_map_k, vm_k, clean_k, x=620, y=100)
        sentinel_k = b.add_constant("__EMPTY__", x=620, y=220)
        is_sentinel_k = b.add_func("equal", [cand_k, sentinel_k], library="core", x=720, y=180)
        final_str_k = b.add_if_else(is_sentinel_k, empty_k, cand_k, x=820, y=100)
        filt_k = b.add_filter_non_empty(final_str_k, x=940, y=100)
        b.add_output(filt_k, "result", x=1060, y=100, uid=output_uid)
    else:
        clean_dict = {k: v for k, v in mapping_dict.items() if v and v != "__EMPTY__"}
        vm_k = b.add_valuemap(clean_k, clean_dict, default_value="", x=400, y=100)
        filt_k = b.add_filter_non_empty(vm_k, x=560, y=100)
        b.add_output(filt_k, "result", x=700, y=100, uid=output_uid)
    return b


def add_strength_core_nodes(b: UdfBuilder, raw_k: int, x: int = 140, y: int = 100) -> int:
    clean_k = b.add_clean_text(raw_k, x=x, y=y)
    comma_k = b.add_constant(",", x=x + 160, y=y + 60)
    empty_k = b.add_constant("", x=x + 160, y=y + 90)
    no_comma_k = b.add_func("translate", [clean_k, comma_k, empty_k], library="core", x=x + 250, y=y)
    no_star_k = b.add_before_or_self(no_comma_k, "**", x=x + 380, y=y)
    no_paren_k = b.add_before_or_self(no_star_k, "(", x=x + 620, y=y)
    core_k = b.add_func("normalize-space", [no_paren_k], library="core", x=x + 860, y=y)
    return core_k


def build_all_udfs() -> list[UdfBuilder]:
    dicts = collect_lookup_dictionaries()
    udfs = []

    # 1. cleanText (uid=1000)
    b = UdfBuilder(
        "cleanText",
        1000,
        "Standardizes text by trimming/collapsing whitespace and converting to uppercase.",
        output_datatype="string",
    )
    raw_k = b.add_input("raw", "string", x=40, y=100)
    clean_k = b.add_clean_text(raw_k, x=180, y=100)
    b.add_output(clean_k, "result", x=460, y=100)
    udfs.append(b)

    # 2. strengthValue (uid=1010)
    b = UdfBuilder(
        "strengthValue",
        1010,
        "Extracts numeric strength value and normalizes concentration per denominator unit (e.g. 25MG/5ML -> 5).",
        output_datatype="decimal",
    )
    raw_k = b.add_input("raw", "string", x=40, y=100)
    core_k = add_strength_core_nodes(b, raw_k, x=140, y=100)
    vm_q_k = b.add_valuemap(core_k, dicts["strength_q"], default_value="", x=1140, y=60)
    v_k = b.add_first_number(core_k, x=1140, y=180)
    empty_k = b.add_constant("", x=1780, y=200)
    has_q_k = b.add_func("not-equal", [vm_q_k, empty_k], library="core", x=1860, y=80)
    val_str_k = b.add_if_else(has_q_k, vm_q_k, v_k, x=1980, y=100)
    filt_k = b.add_filter_non_empty(val_str_k, x=2120, y=100)
    b.add_output(filt_k, "result", x=2260, y=100)
    udfs.append(b)

    # 3. strengthUnit (uid=1020)
    b = UdfBuilder(
        "strengthUnit",
        1020,
        "Extracts and standardizes strength unit using strength_unit.xml (e.g. 25MG/5ML -> mg/mL).",
        output_datatype="string",
    )
    raw_k = b.add_input("raw", "string", x=40, y=100)
    core_k = add_strength_core_nodes(b, raw_k, x=140, y=100)
    v_k = b.add_first_number(core_k, x=1140, y=100)
    empty_k = b.add_constant("", x=1780, y=220)
    has_v_k = b.add_func("not-equal", [v_k, empty_k], library="core", x=1860, y=80)
    after_v_k = b.add_func("substring-after", [core_k, v_k], library="core", x=1860, y=150)
    rest_raw_k = b.add_if_else(has_v_k, after_v_k, empty_k, x=1980, y=100)
    rest_k = b.add_func("normalize-space", [rest_raw_k], library="core", x=2100, y=100)

    # Numerator unit
    num_k = b.add_before_or_self(rest_k, "/", x=2240, y=60)
    nw_k = b.add_first_word(num_k, x=2480, y=60)
    nu_k = b.add_valuemap(nw_k, dicts["unit"], default_value="", x=2840, y=60)

    # Denominator unit
    slash_k = b.add_constant("/", x=2160, y=220)
    den_k = b.add_func("substring-after", [rest_k, slash_k], library="core", x=2240, y=200)
    q_k = b.add_first_number(den_k, x=2380, y=200)
    has_q_k = b.add_func("not-equal", [q_k, empty_k], library="core", x=3060, y=180)
    after_q_k = b.add_func("substring-after", [den_k, q_k], library="core", x=3060, y=250)
    den_unit_k = b.add_if_else(has_q_k, after_q_k, den_k, x=3180, y=200)
    dw_k = b.add_first_word(den_unit_k, x=3300, y=200)
    du_k = b.add_valuemap(dw_k, dicts["unit"], default_value="", x=3660, y=200)

    # Combine nu and du: if nu == "" -> "", else if du != "" -> concat(nu, "/", du) else nu
    has_nu_k = b.add_func("not-equal", [nu_k, empty_k], library="core", x=3800, y=60)
    has_du_k = b.add_func("not-equal", [du_k, empty_k], library="core", x=3800, y=160)
    nu_slash_du_k = b.add_func(
        "concat", [nu_k, slash_k, du_k], library="core", growable=3, growablebasename="value", x=3800, y=240
    )
    with_du_k = b.add_if_else(has_du_k, nu_slash_du_k, nu_k, x=3940, y=140)
    unit_str_k = b.add_if_else(has_nu_k, with_du_k, empty_k, x=4080, y=100)
    filt_k = b.add_filter_non_empty(unit_str_k, x=4220, y=100)
    b.add_output(filt_k, "result", x=4360, y=100)
    udfs.append(b)

    # 4. stdRegulatoryStatus (uid=1030)
    udfs.append(
        build_lookup_udf(
            "stdRegulatoryStatus",
            1030,
            "Maps raw regulatory status to harmonized status (Authorised, Suspended, Pending, Withdrawn, Application withdrawn, Refused).",
            dicts["reg_single"],
            passthrough_unmapped=True,
        )
    )

    # 5. bestRegulatoryStatus (uid=1040)
    udfs.append(
        build_lookup_udf(
            "bestRegulatoryStatus",
            1040,
            "Picks the most active/favourable status among a semicolon-separated list of statuses.",
            dicts["reg_best"],
            passthrough_unmapped=False,
        )
    )

    # 6. stdProductClass (uid=1050)
    udfs.append(
        build_lookup_udf(
            "stdProductClass",
            1050,
            "Standardizes product class to Human, Veterinary, or Disinfectant (also derives Human from FDA ApplType).",
            dicts["pclass"],
            passthrough_unmapped=True,
        )
    )

    # 7. stdDosageForm (uid=1060)
    udfs.append(
        build_lookup_udf(
            "stdDosageForm",
            1060,
            "Maps a single raw dosage form to the controlled target dosage form using dosage_form.xml.",
            dicts["dform_single"],
            passthrough_unmapped=True,
        )
    )

    # 8. dosageFormList (uid=1070)
    udfs.append(
        build_lookup_udf(
            "dosageFormList",
            1070,
            "Maps a semicolon-separated list of dosage forms, deduplicating and sorting the resulting names.",
            dicts["dform_list"],
            passthrough_unmapped=True,
        )
    )

    # 9. stdRoute (uid=1080)
    udfs.append(
        build_lookup_udf(
            "stdRoute",
            1080,
            "Maps a single raw route of administration to standard title case using route.xml.",
            dicts["route_single"],
            passthrough_unmapped=True,
        )
    )

    # 10. routeList (uid=1090)
    udfs.append(
        build_lookup_udf(
            "routeList",
            1090,
            "Maps a semicolon/comma-separated list of routes, deduplicating and sorting the resulting names.",
            dicts["route_list"],
            passthrough_unmapped=True,
        )
    )

    # 11. fdaFormPart (uid=1100)
    b = UdfBuilder(
        "fdaFormPart",
        1100,
        "Extracts dosage form from FDA composite Form column (substring before semicolon).",
        output_datatype="string",
    )
    raw_k = b.add_input("raw", "string", x=40, y=100)
    bef_k = b.add_before_or_self(raw_k, ";", x=180, y=100)
    b.add_output(bef_k, "result", x=460, y=100)
    udfs.append(b)

    # 12. fdaRoutePart (uid=1110)
    b = UdfBuilder(
        "fdaRoutePart",
        1110,
        "Extracts route of administration from FDA composite Form column (substring after semicolon).",
        output_datatype="string",
    )
    raw_k = b.add_input("raw", "string", x=40, y=100)
    semi_k = b.add_constant(";", x=160, y=160)
    aft_k = b.add_func("substring-after", [raw_k, semi_k], library="core", x=260, y=100)
    b.add_output(aft_k, "result", x=420, y=100)
    udfs.append(b)

    # 13. stdAtcCode (uid=1120)
    udfs.append(
        build_lookup_udf(
            "stdAtcCode",
            1120,
            "Standardizes single or semicolon-separated ATC/ATCvet codes, strips '*', fixes 'VO4D'->'V04D', and drops 'Not yet assigned'/'UNASSIGN'.",
            dicts["atc"],
            passthrough_unmapped=True,
            output_uid=112028,
        )
    )

    # 14. stdUnit (uid=1130)
    udfs.append(
        build_lookup_udf(
            "stdUnit",
            1130,
            "Standardizes a single raw measurement unit using strength_unit.xml.",
            {
                u.clean_text(k): (v.get("std") or "__EMPTY__")
                for k, v in u._table("strength_unit.xml").items()
                if u.clean_text(k)
            },
            passthrough_unmapped=True,
        )
    )

    return udfs


def generate_mfd(path: Path = HERE / "wdi_helpers.mfd"):
    udfs = build_all_udfs()
    components_xml = "\n".join(u.to_xml() for u in udfs)
    mfd_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!-- Edited with Altova MapForce 2026r2 -->\n'
        '<mapping xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="35">\n'
        '\t<resources/>\n'
        '\t<component name="defaultmap" uid="1" editable="1" blackbox="0">\n'
        '\t\t<properties SelectedLanguage="builtin"/>\n'
        '\t\t<structure>\n'
        '\t\t\t<children/>\n'
        '\t\t</structure>\n'
        '\t\t<connections/>\n'
        '\t</component>\n'
        f'{components_xml}\n'
        '</mapping>\n'
    )
    path.write_text(mfd_xml, encoding="utf-8")
    print(f"Wrote {path} ({len(mfd_xml):,} bytes, {len(udfs)} UDFs)")


def simulate_mfd_udf(udf_elem: ET.Element, input_value: str) -> str | None:
    """Execute a top-level UDF <component> directly from the parsed wdi_helpers.mfd XML."""
    children = udf_elem.find("./structure/children")
    conns = udf_elem.find("./connections")
    edge_from_for_to = {}
    for edge in conns.findall("edge"):
        edge_from_for_to[edge.attrib["to"]] = edge.attrib["from"]

    comp_by_out_key = {}
    output_comp = None
    for comp in children.findall("component"):
        if comp.attrib.get("kind") == "7":
            output_comp = comp
        targets = comp.find("targets")
        if targets is not None:
            for dp in targets.findall("datapoint"):
                if "key" in dp.attrib:
                    comp_by_out_key[dp.attrib["key"]] = comp

    memo = {}

    def eval_out_key(out_k: str):
        if out_k in memo:
            return memo[out_k]
        comp = comp_by_out_key[out_k]
        kind = comp.attrib["kind"]
        name = comp.attrib["name"]

        def in_val(pos: int):
            dp = comp.find(f"./sources/datapoint[@pos='{pos}']")
            in_k = dp.attrib["key"]
            upstream_out_k = edge_from_for_to[in_k]
            return eval_out_key(upstream_out_k)

        if kind == "6":
            res = input_value
        elif kind == "2":
            res = comp.find("./data/constant").attrib["value"]
        elif kind == "23":
            v = in_val(0)
            if v is None:
                res = None
            else:
                vm = comp.find("./data/valuemap")
                default_val = vm.find("result").attrib.get("defaultValue", "")
                table = {
                    e.attrib["from"]: e.attrib["to"]
                    for e in vm.findall("./valuemapTable/entry")
                }
                res = table.get(v, default_val)
        elif kind == "4":
            cond = in_val(0)
            res = in_val(1) if cond else in_val(2)
        elif kind == "3":
            val = in_val(0)
            cond = in_val(1)
            res = val if (val is not None and cond) else None
        elif kind == "5":
            sources = comp.findall("./sources/datapoint")
            args = [in_val(i) for i in range(len(sources))]
            if any(a is None for a in args):
                res = None
            elif name == "normalize-space":
                res = " ".join(args[0].split())
            elif name == "uppercase":
                res = args[0].upper()
            elif name == "translate":
                s, src, dst = args
                table = {}
                for i, ch in enumerate(src):
                    if ch not in table:
                        table[ch] = dst[i] if i < len(dst) else None
                res = s.translate(str.maketrans(table))
            elif name == "concat":
                res = "".join(args)
            elif name == "substring-before":
                i = args[0].find(args[1])
                res = args[0][:i] if i >= 0 else ""
            elif name == "substring-after":
                i = args[0].find(args[1])
                res = args[0][i + len(args[1]) :] if i >= 0 else ""
            elif name == "contains":
                res = args[1] in args[0]
            elif name == "starts-with":
                res = args[0].startswith(args[1])
            elif name == "equal":
                res = args[0] == args[1]
            elif name == "not-equal":
                res = args[0] != args[1]
            else:
                raise ValueError(f"Unsupported function in simulator: {name}")
        else:
            raise ValueError(f"Unsupported kind in simulator: {kind}")

        memo[out_k] = res
        return res

    out_in_dp = output_comp.find("./sources/datapoint[@pos='0']")
    final_upstream_key = edge_from_for_to[out_in_dp.attrib["key"]]
    return eval_out_key(final_upstream_key)


def verify_mfd(path: Path = HERE / "wdi_helpers.mfd"):
    root = ET.parse(path).getroot()
    udfs = {
        c.attrib["name"]: c
        for c in root.findall("component")
        if c.attrib.get("library") == "user"
    }
    name_map = {
        "strengthValue": "strengthValue",
        "strengthUnit": "strengthUnit",
        "dosageForm": "stdDosageForm",
        "dosageFormList": "dosageFormList",
        "route": "stdRoute",
        "routeList": "routeList",
        "fdaFormPart": "fdaFormPart",
        "fdaRoutePart": "fdaRoutePart",
        "regulatoryStatus": "stdRegulatoryStatus",
        "bestRegulatoryStatus": "bestRegulatoryStatus",
        "productClass": "stdProductClass",
        "stdUnit": "stdUnit",
        "atcCode": "stdAtcCode",
    }
    with open(HERE / "udf_test_cases.csv", encoding="utf-8") as f:
        tests = list(csv.DictReader(f))

    failures = 0
    tested = 0
    for r in tests:
        if r["udf"] not in name_map:
            continue
        tested += 1
        mfd_name = name_map[r["udf"]]
        got = simulate_mfd_udf(udfs[mfd_name], r["input"]) or ""
        if got != r["expected"]:
            failures += 1
            print(f"FAIL {mfd_name}({r['input']!r}) -> {got!r}, expected {r['expected']!r}")
    print(f"Simulated .mfd XML execution: {tested - failures}/{tested} udf_test_cases passed")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    generate_mfd()
    verify_mfd()
