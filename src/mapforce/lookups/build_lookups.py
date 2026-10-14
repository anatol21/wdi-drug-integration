"""Generate the MapForce lookup tables (lookups/*.xml) from explicit standardisation rules.

The rules in this file are the single source of truth. Each table is written as

    <lookup name="dosageForm">
      <entry raw="TABLET, EXTENDED RELEASE" std="Tablet, extended-release"/>
      ...
    </lookup>

`raw` is the source value AFTER the MapForce helper `cleanText` (upper-case + normalize-space),
`std` the standardised target value. `std=""` marks values that carry no information (N/A,
UNKNOWN, ...); the lookup UDFs return nothing for them, so the element is omitted.

Every distinct value found in the raw FDA / DPD / EMA data is written to the table, so the
lookups cover 100% of the current data. The script fails if any value is not covered by a rule.

Usage (from repo root):  python src/mapforce/lookups/build_lookups.py
"""
import re
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RAW = REPO / "data" / "1_raw"
PROCESSED = REPO / "data" / "2_processed"

sys.path.insert(0, str(HERE.parent / "helpers"))
from udf_reference import clean_text, strength_core, first_number, before_or_self, first_word  # noqa: E402


# ----------------------------------------------------------------------------------------------
# Source values
# ----------------------------------------------------------------------------------------------
def load_sources():
    fda_prod = pd.read_csv(RAW / "01_us_drugs_at_fda/Products.txt", sep="\t", dtype=str,
                           encoding="latin-1", keep_default_na=False)
    fda_app = pd.read_csv(RAW / "01_us_drugs_at_fda/Applications.txt", sep="\t", dtype=str,
                          encoding="latin-1", keep_default_na=False)
    fda_ms = pd.read_csv(RAW / "01_us_drugs_at_fda/MarketingStatus_Lookup.txt", sep="\t", dtype=str,
                         encoding="latin-1", keep_default_na=False)
    dpd = pd.read_csv(PROCESSED / "dpd_medicines.csv", dtype=str, encoding="utf-8-sig",
                      keep_default_na=False)
    ema = pd.read_csv(RAW / "02_eu_ema_medicines/ema_medicines.csv", dtype=str,
                      encoding="utf-8-sig", keep_default_na=False)
    return fda_prod, fda_app, fda_ms, dpd, ema


def split_list(values, sep=";"):
    out = set()
    for v in values:
        for part in str(v).split(sep):
            c = clean_text(part)
            if c:
                out.add(c)
    return out


# ----------------------------------------------------------------------------------------------
# Regulatory status   (rank: lower = "better"; used by bestRegulatoryStatus for list values)
# ----------------------------------------------------------------------------------------------
STATUS_RANK = {"Authorised": 1, "Suspended": 2, "Pending": 3, "Withdrawn": 4,
               "Application withdrawn": 5, "Refused": 6}

REGULATORY_STATUS = {
    # Drugs@FDA  (MarketingStatus_Lookup.MarketingStatusDescription)
    "PRESCRIPTION": "Authorised",
    "OVER-THE-COUNTER": "Authorised",
    "FOR FURTHER MANUFACTURING USE": "Authorised",
    "DISCONTINUED": "Withdrawn",
    "NONE (TENTATIVE APPROVAL)": "Pending",
    # EMA  ("Medicine status")
    "AUTHORISED": "Authorised",
    "SUSPENDED": "Suspended",
    "OPINION": "Pending",
    "OPINION UNDER RE-EXAMINATION": "Pending",
    "WITHDRAWN": "Withdrawn",
    "LAPSED": "Withdrawn",
    "EXPIRED": "Withdrawn",
    "REVOKED": "Withdrawn",
    "APPLICATION WITHDRAWN": "Application withdrawn",
    "WITHDRAWN FROM ROLLING REVIEW": "Application withdrawn",
    "REFUSED": "Refused",
    # Health Canada DPD  (current_status)
    "MARKETED": "Authorised",
    "APPROVED": "Authorised",
    "DORMANT": "Authorised",            # DIN still valid, product just not sold for 3+ years
    "CANCELLED POST MARKET": "Withdrawn",
    "CANCELLED (UNRETURNED ANNUAL)": "Withdrawn",
    "CANCELLED (SAFETY ISSUE)": "Withdrawn",
    "AUTHORIZATION BY INTERIM ORDER REVOKED": "Withdrawn",
    "AUTHORIZATION BY INTERIM ORDER EXPIRED": "Withdrawn",
    "CANCELLED PRE MARKET": "Application withdrawn",   # DIN issued, cancelled before marketing
}

# ----------------------------------------------------------------------------------------------
# Product class
# ----------------------------------------------------------------------------------------------
PRODUCT_CLASS = {
    "HUMAN": "Human",
    "VETERINARY": "Veterinary",
    "DISINFECTANT": "Disinfectant",
    "RADIOPHARMACEUTICAL": "Human",     # DPD: radiopharmaceuticals are human-use products
    # Drugs@FDA has no class column; derive it from ApplType (all Drugs@FDA products are human)
    "NDA": "Human",
    "ANDA": "Human",
    "BLA": "Human",
}

# ----------------------------------------------------------------------------------------------
# Dosage form: ordered regex rules, first match wins. Applied to the cleaned raw value.
# FDA values are the part of Products.Form BEFORE ";" (helper fdaFormPart).
# ----------------------------------------------------------------------------------------------
DOSAGE_FORM_EXPLICIT = {
    # FDA multi-form products (several forms in one product) -> Kit
    "CAPSULE, TABLET, CAPSULE, DELAYED REL PELLETS": "Kit",
    "CAPSULE, TABLET, CAPSULE, DELAYED RELEASE": "Kit",
    "CAPSULE, DELAYED REL PELLETS, TABLET": "Kit",
    "CAPSULE, TABLET": "Kit",
    "CAPSULE, TABLET, TABLET": "Kit",
    "CREAM, TABLET": "Kit",
    "CREAM, INSERT": "Kit",
    "CREAM, SUPPOSITORY": "Kit",
    "FOR SOLUTION, TABLET, DELAYED RELEASE": "Kit",
    "FOR SOLUTION, TABLET, FOR SOLUTION": "Kit",
    "FOR SUSPENSION, TABLET": "Kit",
    "INJECTABLE, TABLET": "Kit",
    "TABLET, CHEWABLE, TABLET, CAPSULE": "Kit",
    "TABLET, CHEWABLE, TABLET": "Kit",
    # odd spellings / combinations
    "NJECTION, POWDER, LYOPHILIZED, FOR SOLUTION": "Powder for solution",
    "POWDER, FOR INJECTION SOLUTION, LYOPHILIZED POWDER": "Powder for solution",
    "SOLUTION, ELIXIR": "Elixir",
    "SHAMPOO, SUSPENSION": "Shampoo",
    "LOTION/SHAMPOO": "Lotion",
    "TABLET, ORALLY DISINTEGRATING, DELAYED RELEASE": "Tablet, orally disintegrating",
    "TABLET, ORALLY DISINTEGRATING, EXTENDED RELEASE": "Tablet, orally disintegrating",
    "TABLET, EXTENDED RELEASE, CHEWABLE": "Tablet, chewable",
    "TABLET (CHEWABLE EXTENDED-RELEASE)": "Tablet, chewable",
    "VAGINAL TABLET (EFFERVESCENT)": "Vaginal tablet",
    "FILM, EXTENDED RELEASE": "Transdermal patch",   # FDA: always ;TRANSDERMAL
    "FIBER, EXTENDED RELEASE": "Insert",             # periodontal fibre
    "DRUG-ELUTING CONTACT LENS": "Insert",
    "SEED": "Implant",                               # brachytherapy seeds
    "INHALANT": "Inhalation vapour",
    "PAINT": "Liquid",
    "DOUCHE": "Solution",
    "POD": "Kit",
    "JAM": "Tablet, chewable",
    # no information
    "UNKNOWN": "", "N/A": "", "0-UNASSIGNED": "", "MISCELLANEOUS": "", "BLOOD COLLECTION": "",
}

ER = r"(EXTENDED|SUSTAINED|SLOW|CONTROLLED|COMBINED)"
DR = r"(DELAYED|ENTERIC)"
DOSAGE_FORM_RULES = [
    (r"^VAGINAL TABLET", "Vaginal tablet"),
    (r"^VAGINAL CAPSULE", "Vaginal capsule"),
    (r"ORALLY[- ]DISINTEGRATING", "Tablet, orally disintegrating"),
    (r"^TABLET.*CHEWABLE", "Tablet, chewable"),
    (r"^TABLET.*EFFERVESCENT", "Tablet, effervescent"),
    (r"^TABLET.*(FOR SUSPENSION|DISPERSIBLE)", "Tablet for suspension"),
    (rf"^TABLET.*{ER}", "Tablet, extended-release"),
    (rf"^TABLET.*{DR}", "Tablet, delayed-release"),
    (r"^TABLET", "Tablet"),
    (rf"^CAPSULE.*{ER}", "Capsule, extended-release"),
    (rf"^CAPSULE.*{DR}", "Capsule, delayed-release"),
    (r"^CAPSULE", "Capsule"),
    (r"^(POWDER,? )?FOR SOLUTION|^POWDER FOR SOLUTION|^POWDER, FOR SOLUTION", "Powder for solution"),
    (r"^(POWDER,? )?FOR SUSPENSION|^POWDER FOR SUSPENSION", "Powder for suspension"),
    (r"^(POWDER, METERED|POWDER \(METERED)", "Inhalation powder"),
    (r"^POWDER", "Powder"),
    (r"^(INJECTABLE|INJECTION|VIAL|SYRINGE|PEN$)", "Injection"),
    (r"/DROPS$|^DROPS$", "Drops"),
    (r"^SUSPENSION", "Suspension"),
    (r"^SOLUTION", "Solution"),
    (r"^SYRUP", "Syrup"),
    (r"^ELIXIR", "Elixir"),
    (r"^LIQUID", "Liquid"),
    (r"^CONCENTRATE", "Concentrate"),
    (r"^TINCTURE", "Tincture"),
    (r"^(EMULSION|DISPERSION|LIPOSOMES)", "Emulsion"),
    (r"^CREAM", "Cream"),
    (r"^OINTMENT", "Ointment"),
    (r"^(GEL|JELLY)", "Gel"),
    (r"^LOTION", "Lotion"),
    (r"^SHAMPOO", "Shampoo"),
    (r"^TOOTHPASTE", "Toothpaste"),
    (r"^PASTE", "Paste"),
    (r"^(FOAM|AEROSOL, FOAM|AEROSOL \(FOAM\))", "Foam"),
    (r"^OIL", "Oil"),
    (r"^SOAP", "Soap"),
    (r"^(SPRAY, METERED|SPRAY \(METERED|METERED-DOSE PUMP)", "Spray, metered"),
    (r"^SPRAY", "Spray"),
    (r"^(AEROSOL, METERED|AEROSOL \(METERED|METERED-DOSE AEROSOL)", "Aerosol, metered"),
    (r"^AEROSOL", "Aerosol"),
    (r"^GAS", "Gas"),
    (r"^GRANULE", "Granules"),
    (r"^PELLET", "Pellet"),
    (r"^IMPLANT", "Implant"),
    (r"^(PATCH|SYSTEM|PLASTER|TAPE)", "Transdermal patch"),
    (r"^(FILM|STRIP|WAFER)", "Film"),
    (r"^SUPPOSITORY", "Suppository"),
    (r"^ENEMA", "Enema"),
    (r"^(INSERT|OVULE|TAMPON|DISC)", "Insert"),
    (r"^RING", "Vaginal ring"),
    (r"^INTRAUTERINE DEVICE", "Intrauterine device"),
    (r"^(TROCHE|LOZENGE|PASTILLE)", "Lozenge"),
    (r"^GUM", "Chewing gum"),
    (r"^(BAR|PIECE) ?[,(] ?CHEWABLE", "Tablet, chewable"),
    (r"^(SWAB|WIPE|PAD|CLOTH|SPONGE|DRESSING|CORD|FLOSS)", "Impregnated pad"),
    (r"^(STICK|PENCIL)", "Stick"),
    (r"^GLOBULES", "Globules"),
    (r"^(TEA|LEAF)", "Herbal tea"),
    (r"^MOUTHWASH", "Mouthwash"),
    (r"^BOLUS", "Bolus"),
    (r"^DRUG PREMIX", "Premix"),
    (r"^(KIT|PACKAGE)", "Kit"),
]

# ----------------------------------------------------------------------------------------------
# Route. FDA: Products.Form part AFTER ";" split on ","; DPD: routes split on ";".
# Unlisted routes default to Title Case of the cleaned value (rule at the end).
# ----------------------------------------------------------------------------------------------
ROUTE_EXPLICIT = {
    "ORAL-20": "Oral", "ORAL-21": "Oral", "ORAL-28": "Oral", "ORAL SUSPENSION": "Oral",
    "ORALLY DISINTEGRATING": "Oral", "ORAL AND TABLET": "Oral", "ENTERAL": "Oral",
    "IV (INFUSION)": "Intravenous", "PERFUSION": "Intravenous",
    "IM-IV": "Intramuscular; Intravenous",
    "SUBCUTANEOUS LYOPHILIZED POWER": "Subcutaneous",
    "INJECTION": "Injection", "INJECTABLE": "Injection", "PARENTERAL (UNSPECIFIED)": "Injection",
    "SOFT TISSUE INJECTION": "Injection",
    "IMPLANTATION": "Implantation", "IMPLANT": "Implantation",
    "INTRA-ARTICULAR": "Intra-articular", "INTRA-ARTERIAL": "Intra-arterial",
    "INTRA-ANAL": "Rectal", "INTRAVESICULAR": "Intravesical",
    "INTRACUTANEOUS": "Intradermal",
    "SPINAL": "Intraspinal", "SUBARACHNOIDAL": "Intrathecal",
    "BLOCK/INFILTRATION": "Infiltration", "NERVE BLOCK": "Infiltration",
    "HAEMODIALYSIS": "Haemodialysis", "HAEMODIALYSIS (INTRAPERITONEAL)": "Intraperitoneal",
    "TOPICAL (HOUSEHOLD)": "Topical", "TOPICAL (COMMERCIAL)": "Topical",
    "TOPICAL (HOSPITAL/HC FACILITIES)": "Topical", "TOPICAL (FOOD PREMISES)": "Topical",
    "UDDER WASH": "Topical", "TEAT-DIP": "Topical", "TEAT DILATOR": "Intramammary",
    "ARTHOGRAPHY": "Intra-articular", "CYSTOGRAPHY": "Intravesical",
    "ENDOTRACHEAL": "Intratracheal", "INTUBING": "Intratracheal",
    "INTRAVITREAL": "Intravitreal", "INTRACAMERAL": "Intraocular",
    # not a route (FDA strength / form fragments, packaging) or unknown
    "": "", "N/A": "", "UNKNOWN": "", "NIL": "", "0-UNASSIGNED": "", "MISCELLANEOUS": "",
    "REFER (SEE DOSAGE FORM)": "", "LABORATORY TEST": "",
    "FILM COATED": "", "SOLUTION": "", "SUSPENSION": "", "POWDER": "", "FOR SOLUTION": "",
    "CONCENTRATE": "", "DROPS": "", "EXTENDED RELEASE": "", "SINGLE-USE": "", "SINGLE-DOSE": "",
    "MULTIDOSE": "", "PREFILLED": "", "FOR RX COMPOUNDING": "",
}
ROUTE_RULES = [
    (r"^DISINFECTANT", "Disinfectant"),
    (r"^INTRAINTESTINAL", "Intestinal"),
]


def route_default(raw):
    return raw.capitalize()   # e.g. INTRATHECAL -> Intrathecal (standard spelling, Title case)


# ----------------------------------------------------------------------------------------------
# Strength units. Key = first word of the numerator or the denominator unit of a strength
# (see udf_reference.strength_unit). Same table for numerator and denominator.
# ----------------------------------------------------------------------------------------------
STRENGTH_UNIT = {
    # mass
    "MG": "mg", "GM": "g", "G": "g", "GMBASE": "g", "MCG": "mcg", "UG": "mcg", "UGM": "mcg",
    "NG": "ng", "KG": "kg",
    # volume
    "ML": "mL", "L": "L", "MCL": "mcL",
    # ratio
    "%": "%", "PPM": "ppm",
    # biological / activity units
    "IU": "IU", "MIU": "MIU", "KIU": "KIU", "UNITS": "U", "UNIT": "U", "U": "U", "USP": "USP U",
    "PRESSOR": "U", "CSR": "CSR U", "TU": "TU", "LF": "Lf", "GAL": "GAL", "GALU": "GALU",
    # amount of substance
    "MEQ": "mEq", "MMOL": "mmol", "MCMOL": "mcmol",
    # radioactivity
    "CI": "Ci", "MCI": "mCi", "UCI": "mcCi", "MCCI": "mcCi", "CU": "Ci",
    "MBQ": "MBq", "GBQ": "GBq", "KBQ": "kBq",
    # vaccines / cell & gene therapy
    "CELLS": "cells", "CCID50": "CCID50", "TCID50": "TCID50", "LOG10": "log10", "PFU": "PFU",
    "CFU": "CFU", "FFU": "FFU", "VP": "VP", "VG": "vg", "BVG": "vg", "GENOME": "genome copies",
    "DOSE": "dose",
    # homeopathic potencies (kept as-is)
    "X": "X", "D": "D", "C": "C", "CH": "CH", "DH": "DH", "K": "K", "CMK": "CMK", "XMK": "XMK",
    "M": "M", "LM": "LM", "TM": "TM", "B": "B",
    # denominators (per ...)
    "VIAL": "vial", "AMP": "ampoule", "BOT": "bottle", "PACKET": "packet", "KIT": "kit",
    "SCOOPFUL": "scoop", "TEASPOONFUL": "teaspoon", "BAR": "bar", "PATCH": "patch",
    "IMPLANT": "implant", "SPRAY": "spray", "INH": "actuation", "ACTUATION": "actuation",
    "ACTIVATION": "actuation", "DELIVERY": "actuation", "HR": "h", "DAY": "day",
    "SQ": "cm2", "GENERATOR": "generator", "CYLINDER": "cylinder",
    # no unit information
    "NIL": "", "TRACE": "", "W": "", "V": "", "COPPER": "", "N/A": "", "UNKNOWN": "",
}


# ----------------------------------------------------------------------------------------------
def apply_rules(raw, explicit, rules, default=None):
    if raw in explicit:
        return explicit[raw]
    for pattern, std in rules:
        if re.search(pattern, raw):
            return std
    if default is not None:
        return default(raw)
    return None


def write_table(name, filename, mapping, extra_attr=None):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<!-- GENERATED by build_lookups.py - edit the rules there, not this file. -->',
             f'<lookup name="{name}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
             f'xsi:noNamespaceSchemaLocation="lookup.xsd">']
    for raw in sorted(mapping):
        std = mapping[raw]
        extra = ""
        if extra_attr:
            k, fn = extra_attr
            extra = f" {k}={quoteattr(fn(std))}"
        lines.append(f"  <entry raw={quoteattr(raw)} std={quoteattr(std)}{extra}/>")
    lines.append("</lookup>")
    (HERE / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {filename:<24} {len(mapping):4d} entries")


def build_table(observed, explicit, rules, default=None, label=""):
    table, missing = {}, []
    for raw in sorted(observed | set(explicit)):
        std = apply_rules(raw, explicit, rules, default)
        if std is None:
            missing.append(raw)
        else:
            table[raw] = std
    if missing:
        raise SystemExit(f"{label}: no rule for {missing}")
    return table


def main():
    fda_prod, fda_app, fda_ms, dpd, ema = load_sources()

    # --- regulatory status
    observed = (split_list(fda_ms.MarketingStatusDescription) | split_list(ema["Medicine status"])
                | split_list(dpd.current_status))
    status = build_table(observed, REGULATORY_STATUS, [], label="regulatoryStatus")

    # --- product class
    observed = (split_list(dpd.product_class) | split_list(ema.Category)
                | split_list(fda_app.ApplType))
    pclass = build_table(observed, PRODUCT_CLASS, [], label="productClass")

    # --- dosage form
    fda_forms = {clean_text(before_or_self(f, ";")) for f in fda_prod.Form}
    observed = {f for f in fda_forms if f} | split_list(dpd.dosage_forms)
    dform = build_table(observed, DOSAGE_FORM_EXPLICIT, DOSAGE_FORM_RULES, label="dosageForm")

    # --- route
    fda_routes = set()
    for f in fda_prod.Form:
        route_part = f.split(";", 1)[1] if ";" in f else ""
        fda_routes |= split_list([route_part], sep=",")
    observed = fda_routes | split_list(dpd.routes)
    route = build_table(observed, ROUTE_EXPLICIT, ROUTE_RULES, route_default, label="route")

    # --- strength units (numerator first word + denominator unit word of every strength)
    observed = set()
    tokens = [t for s in fda_prod.Strength for t in s.split(";")]
    tokens += [t for s in dpd.strengths for t in s.split(";")]
    for t in tokens:
        core = strength_core(t)
        num = first_number(core)
        if num is None:
            continue
        rest = core[core.find(num) + len(num):].strip()
        numerator = before_or_self(rest, "/")
        denominator = rest[len(numerator) + 1:] if "/" in rest else ""
        if first_word(numerator):
            observed.add(first_word(numerator))
        q = first_number(denominator)
        den_unit = denominator[denominator.find(q) + len(q):] if q else denominator
        if first_word(den_unit):
            observed.add(first_word(den_unit))
    unknown = sorted(observed - set(STRENGTH_UNIT))
    units = {k: v for k, v in STRENGTH_UNIT.items()}
    for k in unknown:          # unseen words: keep them visible but mark as no-unit
        units[k] = ""
    if unknown:
        print(f"  NOTE strength units without a rule (mapped to no unit): {unknown}")

    print("Writing lookup tables:")
    write_table("regulatoryStatus", "regulatory_status.xml", status,
                extra_attr=("sortKey", lambda s: f"{STATUS_RANK[s]}-{s}"))
    write_table("productClass", "product_class.xml", pclass)
    write_table("dosageForm", "dosage_form.xml", dform)
    write_table("route", "route.xml", route)
    write_table("strengthUnit", "strength_unit.xml", units)

    # sanity: all std values must be valid schema vocabulary
    assert set(status.values()) <= set(STATUS_RANK)
    assert set(pclass.values()) <= {"Human", "Veterinary", "Disinfectant"}
    print("Distinct standardised values: "
          f"status={len(set(status.values()))}, class={len(set(pclass.values()))}, "
          f"dosageForm={len(set(dform.values()) - {''})}, route={len(set(route.values()) - {''})}, "
          f"unit={len(set(units.values()) - {''})}")


if __name__ == "__main__":
    main()
