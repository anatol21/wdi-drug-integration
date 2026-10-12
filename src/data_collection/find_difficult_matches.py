import pandas as pd

# 1. Load Drugs@FDA (Products.txt + Applications.txt)
fda_prod = pd.read_csv("data/1_raw/US Drug/Products.txt", sep="\t", dtype=str, on_bad_lines="skip")
fda_app = pd.read_csv("data/1_raw/US Drug/Applications.txt", sep="\t", dtype=str, on_bad_lines="skip")
fda = pd.merge(fda_prod, fda_app, on="ApplNo", how="left")
fda["brand_norm"] = fda["DrugName"].astype(str).str.upper().str.strip()
fda["brand_prefix"] = fda["brand_norm"].str.split().str[0]

# 2. Load EMA Medicines (EU Drug.csv)
ema = pd.read_csv("data/1_raw/EU Drug.csv", dtype=str)
ema["brand_norm"] = ema["Name of medicine"].astype(str).str.upper().str.strip()
ema["brand_prefix"] = ema["brand_norm"].str.split().str[0]

# 3. Load Health Canada DPD (drug.txt + ingred.txt + comp.txt)
dpd_drug = pd.read_csv("data/1_raw/03. DPD/allfiles/drug.txt", header=None, dtype=str)
dpd_ingred = pd.read_csv("data/1_raw/03. DPD/allfiles/ingred.txt", header=None, dtype=str)
dpd_comp = pd.read_csv("data/1_raw/03. DPD/allfiles/comp.txt", header=None, dtype=str)

# Aggregate multiple active ingredients per DRUG_CODE (column 0)
dpd_ing_agg = (
    dpd_ingred.groupby(0)[2]
    .apply(lambda s: "; ".join(sorted(set(s.dropna()))))
    .reset_index()
    .rename(columns={0: "DRUG_CODE", 2: "DPD_Ingredient"})
)

dpd = (
    dpd_drug[[0, 3, 4]]
    .rename(columns={0: "DRUG_CODE", 3: "DIN", 4: "DPD_Brand"})
    .merge(dpd_ing_agg, on="DRUG_CODE", how="left")
    .merge(
        dpd_comp[[0, 3]].rename(columns={0: "DRUG_CODE", 3: "DPD_Company"}),
        on="DRUG_CODE",
        how="left",
    )
)
dpd["brand_norm"] = dpd["DPD_Brand"].astype(str).str.upper().str.strip()
dpd["brand_prefix"] = dpd["brand_norm"].str.split().str[0]

# 4a. Find exact 3-way brand matches where active substance strings differ (e.g., VERKAZIA, AIMOVIG)
common_exact_brands = (
    set(fda["brand_norm"]) & set(ema["brand_norm"]) & set(dpd["brand_norm"])
)
diff_substance_exact_brands = []
for b in sorted(common_exact_brands):
    f_ing = str(fda.loc[fda["brand_norm"] == b, "ActiveIngredient"].iloc[0]).upper().strip()
    e_ing = str(ema.loc[ema["brand_norm"] == b, "Active substance"].iloc[0]).upper().strip()
    d_ing = str(dpd.loc[dpd["brand_norm"] == b, "DPD_Ingredient"].iloc[0]).upper().strip()
    if f_ing != e_ing or f_ing != d_ing:
        diff_substance_exact_brands.append(b)

# 4b. Find 3-way brand-prefix matches where BOTH Brand Name AND Active Substance differ (e.g., SEEBRI)
common_prefixes = (
    set(fda["brand_prefix"].dropna())
    & set(ema["brand_prefix"].dropna())
    & set(dpd["brand_prefix"].dropna())
)
diff_brand_and_substance_prefixes = []
for p in sorted(common_prefixes):
    if len(p) < 5:
        continue
    fb = str(fda.loc[fda["brand_prefix"] == p, "DrugName"].iloc[0]).upper().strip()
    eb = str(ema.loc[ema["brand_prefix"] == p, "Name of medicine"].iloc[0]).upper().strip()
    db = str(dpd.loc[dpd["brand_prefix"] == p, "DPD_Brand"].iloc[0]).upper().strip()

    fs = str(fda.loc[fda["brand_prefix"] == p, "ActiveIngredient"].iloc[0]).upper().strip()
    es = str(ema.loc[ema["brand_prefix"] == p, "Active substance"].iloc[0]).upper().strip()
    ds = str(dpd.loc[dpd["brand_prefix"] == p, "DPD_Ingredient"].iloc[0]).upper().strip()

    if len({fb, eb, db}) > 1 and len({fs, es, ds}) == 3:
        diff_brand_and_substance_prefixes.append(p)

print(f"Total 3-way exact brand matches: {len(common_exact_brands)}")
print(
    f"  -> With differing active substance strings: {len(diff_substance_exact_brands)} "
    f"(includes VERKAZIA: {'VERKAZIA' in diff_substance_exact_brands}, "
    f"AIMOVIG: {'AIMOVIG' in diff_substance_exact_brands})"
)
print(
    f"3-way brand-prefix matches where both Brand Name AND Active Substance differ: "
    f"{len(diff_brand_and_substance_prefixes)} "
    f"(includes SEEBRI: {'SEEBRI' in diff_brand_and_substance_prefixes})\n"
)

# 5. Print detailed records for VERKAZIA, SEEBRI, and AIMOVIG
target_prefixes = ["VERKAZIA", "SEEBRI", "AIMOVIG"]

for prefix in target_prefixes:
    print("=" * 85)
    print(f"EXAMPLE MEDICINE: {prefix}")
    print("-" * 85)

    f_rows = fda[fda["brand_prefix"] == prefix][
        ["ApplNo", "DrugName", "ActiveIngredient", "SponsorName"]
    ].drop_duplicates()
    print("[Drugs@FDA]")
    print(f_rows.to_string(index=False) if not f_rows.empty else "  Not present")

    e_rows = ema[ema["brand_prefix"] == prefix][
        [
            "EMA product number",
            "Name of medicine",
            "Active substance",
            "Marketing authorisation developer / applicant / holder",
        ]
    ].drop_duplicates()
    print("\n[EMA Medicines]")
    print(e_rows.to_string(index=False) if not e_rows.empty else "  Not present")

    d_rows = dpd[dpd["brand_prefix"] == prefix][
        ["DIN", "DPD_Brand", "DPD_Ingredient", "DPD_Company"]
    ].drop_duplicates()
    print("\n[Health Canada DPD]")
    print(d_rows.to_string(index=False) if not d_rows.empty else "  Not present")
    print()