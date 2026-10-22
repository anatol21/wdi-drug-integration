"""Consolidate Health Canada DPD products (one row per DIN) into medicine entities.

Input
    data/2_processed/dpd_products.csv   58,137 products, the DRUG_CODE join of the DPD tables
                                        (built by dpd_extract.ipynb)
    data/2_processed/dpd_medicines.csv  42,042 medicines grouped with the older medicine key
Output
    data/2_processed/dpd_entities.csv   41,636 entities, one row per normalized
                                        brand name + sorted active substances

The entity key is the same one entity_count.py uses (normalize() is imported from there), so
medicine_id matches data/3_profiling/entity_count/dpd_normalized_entities.csv exactly.

Multi-valued source fields are joined with "; " so the MapForce helpers can resolve them:
    current_status -> bestRegulatoryStatus, product_class -> stdProductClass,
    atc_code -> stdAtcCode, dosage_forms -> dosageFormList, routes -> routeList.
Fields that need a single value are resolved here:
    brand_name     most frequent raw brand name among the entity's DINs
    licence_holder most frequent DIN owner; ties go to the DIN with the best status,
                   then the most recent status date
    biosimilar     "Yes" if any DIN is a biosimilar
    status_date    latest current_status_date among the DINs that carry the best status
                   (candidate for caStatusDate)
    approval_date  earliest approval date of any DIN
"""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "2_processed"
ENTITY_COUNT_FILE = REPO_ROOT / "data" / "3_profiling" / "entity_count" / "dpd_normalized_entities.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from entity_count import normalize  # noqa: E402  (same key as the entity count)

# Same ranking as bestRegulatoryStatus (lookups/regulatory_status.xml sortKey)
STATUS_RANK = {
    "MARKETED": 1, "APPROVED": 1, "DORMANT": 1,
    "CANCELLED POST MARKET": 4, "CANCELLED (UNRETURNED ANNUAL)": 4, "CANCELLED (SAFETY ISSUE)": 4,
    "AUTHORIZATION BY INTERIM ORDER EXPIRED": 4, "AUTHORIZATION BY INTERIM ORDER REVOKED": 4,
    "CANCELLED PRE MARKET": 5,
}


def join_unique(values, sort=True):
    """Distinct non-empty values joined with "; " (splitting values that are already lists)."""
    items = []
    for v in values.dropna():
        items.extend(x.strip() for x in str(v).split(";") if x.strip())
    items = list(dict.fromkeys(items))
    if sort:
        items = sorted(items)
    return "; ".join(items) if items else pd.NA


def mode_first(values):
    """Most frequent value; ties keep the first value in the (pre-sorted) order."""
    values = values.dropna()
    if values.empty:
        return pd.NA
    counts = values.value_counts(sort=False)
    best = counts.max()
    return next(v for v in values if counts[v] == best)


def main():
    products = pd.read_csv(PROCESSED_DIR / "dpd_products.csv", dtype="string", encoding="utf-8-sig")
    medicines = pd.read_csv(PROCESSED_DIR / "dpd_medicines.csv", dtype="string", encoding="utf-8-sig")

    # Entity key per old medicine, computed exactly like entity_count.py
    medicines["brand_key"] = medicines["brand_name"].map(normalize)
    medicines["substance_key"] = medicines["active_substances"].map(lambda v: normalize(v, substance_list=True))
    medicines = medicines[medicines["brand_key"].ne("") & medicines["substance_key"].ne("")]
    medicines["entity_id"] = medicines["brand_key"] + "|" + medicines["substance_key"]
    old_to_new = medicines.set_index("medicine_id")["entity_id"]

    products["entity_id"] = products["medicine_id"].map(old_to_new)
    dropped = products["entity_id"].isna()
    print(f"Products: {len(products):,}  without brand name or active substance (dropped): {dropped.sum():,}")
    products = products[~dropped].copy()

    # Order DINs best-first so ties in mode_first() go to the best / most recent DIN
    products["status_rank"] = products["current_status"].map(STATUS_RANK).fillna(9)
    products = products.sort_values(["entity_id", "status_rank", "current_status_date"],
                                    ascending=[True, True, False])

    best_rank = products.groupby("entity_id")["status_rank"].transform("min")
    status_date = products[products["status_rank"].eq(best_rank)].groupby("entity_id")["current_status_date"].max()

    g = products.groupby("entity_id", sort=True)
    entities = pd.DataFrame({
        "brand_name": g["brand_name"].agg(mode_first),
        "licence_holder": g["manufacturer"].agg(mode_first),
        "licence_holders_all": g["manufacturer"].agg(join_unique),
        "product_class": g["product_class"].agg(join_unique),
        "atc_code": g["atc_code"].agg(join_unique),
        "biosimilar": g["biosimilar"].agg(lambda s: "Yes" if s.eq("Yes").any() else "No"),
        "schedule": g["schedule"].agg(join_unique),
        "dosage_forms": g["dosage_form"].agg(join_unique),
        "routes": g["route"].agg(join_unique),
        "current_status": g["current_status"].agg(join_unique),
        "status_date": status_date,
        "approval_date": g["approval_date"].min(),
        "first_marketed_date": g["first_marketed_date"].min(),
        "number_of_dins": g.size(),
        "drug_codes": g["drug_code"].agg(lambda s: "; ".join(s)),
    })

    # Substances and strengths come from the old medicine rows (base substance names, "10 MG; 25 MG")
    mg = medicines.groupby("entity_id")
    entities["active_substances"] = mg["active_substances"].agg(join_unique)
    entities["strengths"] = mg["strengths"].agg(lambda s: join_unique(s, sort=False))

    entities = entities.rename_axis("medicine_id").reset_index()
    columns = ["medicine_id", "brand_name", "active_substances", "strengths", "licence_holder",
               "licence_holders_all", "product_class", "atc_code", "biosimilar", "schedule",
               "dosage_forms", "routes", "current_status", "status_date", "approval_date",
               "first_marketed_date", "number_of_dins", "drug_codes"]
    out = PROCESSED_DIR / "dpd_entities.csv"
    entities[columns].to_csv(out, index=False, encoding="utf-8-sig")

    # Checks against the entity count
    expected = set(pd.read_csv(ENTITY_COUNT_FILE, dtype="string", encoding="utf-8-sig")["medicine_id"])
    got = set(entities["medicine_id"])
    print(f"Entities: {len(entities):,}  (expected {len(expected):,})")
    print(f"Ids missing vs entity count: {len(expected - got)}  extra: {len(got - expected)}")
    print(f"DINs covered: {entities['number_of_dins'].sum():,}")
    assert got == expected, "medicine_id set differs from dpd_normalized_entities.csv"
    print(f"Saved {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
