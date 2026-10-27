# Altova MapForce Data Mapping: Target Schema & Helper Functions

This directory contains the Phase I data translation assets for integrating pharmaceutical drug data from **Drugs@FDA (US)**, **EMA Medicines (EU)**, and **Health Canada DPD (CA)**.

---

## 1. Directory Structure

```text
src/mapforce/
├── schema/
│   ├── medicines.xsd           # Shared target XML Schema (16 attributes + metadata)
│   ├── medicines.schema.json   # JSON Schema equivalent
│   ├── sample_medicines.xml    # Minimal dummy sample demonstrating all conventions
│   ├── sample_medicines.json   # Equivalent JSON dummy sample
│   └── check_schema.py         # Validator for XSD/JSON samples & output files
├── lookups/
│   ├── lookup.xsd              # XML Schema for lookup files
│   ├── build_lookups.py        # Python script generating lookups from observed raw values
│   ├── regulatory_status.xml   # Harmonized regulatory statuses (Authorised, Withdrawn, etc.)
│   ├── product_class.xml       # Product classes (Human, Veterinary, Disinfectant)
│   ├── dosage_form.xml         # Standardized dosage forms (Tablet, Capsule, Injection, etc.)
│   ├── route.xml               # Standardized administration routes (Oral, Intravenous, etc.)
│   └── strength_unit.xml       # Standardized measurement units (mg, mL, %, U/mL, etc.)
└── helpers/
    ├── README.md               # Detailed UDF documentation & wiring diagrams
    ├── wdi_helpers.mfd         # Altova MapForce UDF library for Built-in execution
    ├── wdi_helpers.mfd         # Altova MapForce UDF library for Built-in execution
    ├── build_helpers_mfd.py    # Generator & simulator for wdi_helpers.mfd
    ├── wdi_helpers.xslt        # Reusable XSLT 3.0 / 2.0 helper function library
    ├── udf_reference.py        # Python test oracle & dataset coverage audit
    └── udf_test_cases.csv      # 107 unit tests covering all functions and edge cases
```

---

## 2. Integrated Target Schema (`medicines.xsd` / `medicines.schema.json`)

The target schema represents a **medicine entity** (`brandName` + `activeSubstances`) from one jurisdiction. It contains the 16 attributes agreed upon in Table 2 of the project outline, plus `id` and `source` metadata needed by PyDI for Phase II (Identity Resolution) and Phase III (Data Fusion):

```xml
<medicines>
  <medicine>
    <id>FDA_VERKAZIA|CYCLOSPORINE</id>
    <source>FDA</source>
    <brandName>VERKAZIA</brandName>
    <activeSubstances>
      <activeSubstance>CYCLOSPORINE</activeSubstance>
    </activeSubstances>
    <activeSubstanceCount>1</activeSubstanceCount>
    <licenceHolder>HARROW EYE</licenceHolder>
    <regulatoryStatus>Authorised</regulatoryStatus>
    <productClass>Human</productClass>
    <generic>false</generic>
    <dosageForm>Emulsion</dosageForm>
    <route>Ophthalmic</route>
    <strengths>
      <strength>
        <value>0.1</value>
        <unit>%</unit>
      </strength>
    </strengths>
    <usApprovalDate>2021-06-23</usApprovalDate>
  </medicine>
</medicines>
```

### Key Conventions
1. **Omit Missing Values:** Do not emit empty tags like `<atcCode/>`. If a field is missing in the source, omit the element entirely.
2. **Repeating Elements:** Lists use wrapper elements:
   * `<activeSubstances>` containing repeated `<activeSubstance>`
   * `<strengths>` containing repeated `<strength>` with `<value>` (numeric) and `<unit>` (string)
3. **Controlled Vocabularies:**
   * `regulatoryStatus`: `Authorised`, `Suspended`, `Pending`, `Withdrawn`, `Application withdrawn`, `Refused`
   * `productClass`: `Human`, `Veterinary`, `Disinfectant`
4. **Dates:** ISO 8601 format (`YYYY-MM-DD`).

### Entity Consolidation Rules (Pre-Mapping Aggregations)

When consolidating multiple source product or application records into a single medicine entity (`brandName` + `activeSubstances`), all sources (Drugs@FDA, Health Canada DPD, EMA) follow these shared aggregation conventions:

| Attribute Group | Target Attribute(s) | Consolidation Policy | Rationale & Resolution Rule |
| :--- | :--- | :--- | :--- |
| **Booleans** | `generic` (FDA), `biosimilar` (DPD), `orphanMedicine` (EMA) | **Unanimity (FDA `generic`) / Any-positive (DPD `biosimilar`)** | **FDA `generic`:** Uses **Option 2 (Unanimity)**: `true` if all contributing applications are `ANDA`; `false` if all are `NDA`/`BLA`; **omitted** (`null`) if mixed (`NDA` and `ANDA`). The ~375 mixed entities represent authorized generics or co-branded innovator/generic submissions and are intentionally omitted as *Not Missing At Random (NMAR)* since neither boolean value is strictly true. <br>**DPD `biosimilar`:** Uses **Option 1 (Any-positive)**: `true` if any contributing DIN is approved as a biosimilar, since biosimilarity is a regulatory drug-line designation in Canada. |
| **Single-Valued Text** | `licenceHolder` (FDA `SponsorName`, DPD `manufacturer`) | **Plurality Vote (`mode_first`) + Tie-Breaking** | The sponsor/manufacturer with the most contributing product records is chosen. Ties are broken deterministically: select the owner of the record with the highest regulatory status (Authorised/Marketed > Withdrawn/Cancelled), then the most recent status/approval date. |
| **Status Hierarchy** | `regulatoryStatus` | **Precedence Ranking** (`bestRegulatoryStatus`) | Highest-precedence active status wins: $\text{Authorised} > \text{Suspended} > \text{Pending} > \text{Withdrawn} > \text{Application withdrawn} > \text{Refused}$. |
| **Product Class** | `productClass` | **Human-Precedence** (`stdProductClass`) | Prioritizes `Human` if both `Human` and `Veterinary`/`Disinfectant` products coexist under the same entity key. |
| **Multi-Valued Lists** | `dosageForm`, `route` | **Deduplicated Set Union** (`dosageFormList`, `routeList`) | Unique values standardized, deduplicated, sorted alphabetically, and joined with `"; "` (e.g., `"Liquid; Solution"`). |
| **Strengths** | `strengths` | **Pair Union** (`strengthValue` + `strengthUnit`) | All distinct numeric `(value, unit)` pairs across all contributing products are preserved as repeated `<strength>` elements. |
| **Dates** | `usApprovalDate`, `euAuthorisationDate`, `caStatusDate` | **Earliest Approval / Latest Active Status** | Approval date takes the earliest approval across contributing records. Status date takes the latest status date among records sharing the highest status rank. |

---

## 3. Mapper Plug-in Specifications

### A. Drugs@FDA Mapper (`fda_mapping.mfd`)
* **Source Tables:**
  * Join `Products.txt` with `Applications.txt` on `ApplNo` (note: 11 product rows have no matching `ApplNo` in `Applications.txt`, and 1 row `ApplNo=221337` `MEDICAL AIR, USP` has an empty `ActiveIngredient`—drop empty `ActiveIngredient` when consolidating entities, just like `entity_count.py`).
  * Join `MarketingStatus.txt` and `MarketingStatus_Lookup.txt` on `MarketingStatusID`.
  * When pre-consolidating products into medicine entities, split `Products.Form` into `fdaFormPart(Form)` and `fdaRoutePart(Form)` *before* joining distinct values across products with `"; "`.
* **Field Connections:**
  * `id`: `concat("FDA_", medicine_id)` (or `concat("FDA_", DrugName, "|", ActiveIngredient)`)
  * `source`: Constant `"FDA"`
  * `brandName`: `DrugName`
  * `activeSubstances`: `tokenize(ActiveIngredient, ';')`
  * `activeSubstanceCount`: `count(activeSubstances)`
  * `licenceHolder`: `SponsorName`
  * `regulatoryStatus`: `bestRegulatoryStatus(MarketingStatusDescription)` (or `stdRegulatoryStatus` for single value)
  * `productClass`: `stdProductClass(ApplType)` $\rightarrow$ `"Human"` (or constant `"Human"` if `ApplNo` is missing from `Applications.txt`)
  * `dosageForm`: `dosageFormList(dosage_forms)` (or `stdDosageForm(fdaFormPart(Form))` per product)
  * `route`: `routeList(routes)` (or `stdRoute(fdaRoutePart(Form))` per product; handles both `,` and `;` separators)
  * `generic`: Under Option 2 (Unanimity): `true` when all applications are `ANDA`, `false` when all are `NDA`/`BLA`, omitted when mixed. Map directly from consolidated boolean/flag, or via `equal(generic, "true")`.
  * `strengths`: For each token in `tokenize(Strength, ';')`, map `strengthValue` $\rightarrow$ `value` and `strengthUnit` $\rightarrow$ `unit`.
  * `usApprovalDate`: Earliest non-empty `substring(SubmissionStatusDate, 1, 10)` where `SubmissionStatus = "AP"` (note: 8 `AP` rows in `Submissions.txt` have an empty `SubmissionStatusDate`).

### B. Health Canada DPD Mapper (`dpd_mapping.mfd`)
* **Source Table:** `data/2_processed/dpd_medicines.csv`
* **Field Connections:**
  * `id`: `concat("DPD_", medicine_id)`
  * `source`: Constant `"DPD"`
  * `brandName`: `brand_name`
  * `activeSubstances`: `tokenize(active_substances, ';')`
  * `activeSubstanceCount`: `count(activeSubstances)`
  * `licenceHolder`: `licence_holder`
  * `regulatoryStatus`: `bestRegulatoryStatus(current_status)`
  * `productClass`: `stdProductClass(product_class)`
  * `atcCode`: `stdAtcCode(atc_code)`
  * `biosimilar`: `equal(biosimilar, "Yes")`
  * `dosageForm`: `dosageFormList(dosage_forms)`
  * `route`: `routeList(routes)`
  * `strengths`: For each token in `tokenize(strengths, ';')`, map `strengthValue` $\rightarrow$ `value` and `strengthUnit` $\rightarrow$ `unit`.
  * `caStatusDate`: `approval_date`

### C. EMA Medicines Mapper (`ema_mapping.mfd`)
* **Source Table:** `data/1_raw/02_eu_ema_medicines/ema_medicines.csv`
* **Field Connections:**
  * `id`: `concat("EMA_", medicine_id)`
  * `source`: Constant `"EMA"`
  * `brandName`: `Name of medicine`
  * `activeSubstances`: `tokenize(Active substance, ';')`
  * `activeSubstanceCount`: `count(activeSubstances)`
  * `licenceHolder`: `Marketing authorisation developer / applicant / holder`
  * `regulatoryStatus`: `stdRegulatoryStatus(Medicine status)`
  * `productClass`: `stdProductClass(Category)`
  * `atcCode`: `stdAtcCode(concat(ATC code (human), ";", ATCvet code (veterinary)))`
  * `generic`: `equal(Generic, "Yes")`
  * `biosimilar`: `equal(Biosimilar, "Yes")`
  * `orphanMedicine`: `equal(Orphan medicine, "Yes")`
  * `euAuthorisationDate`: Format `Marketing authorisation date` (DD/MM/YYYY) to ISO (YYYY-MM-DD).

---

## 4. Verification & Validation

To validate generated XML or JSON output files against the target schema:

```bash
# Validate sample instances
python src/mapforce/schema/check_schema.py

# Validate any MapForce output XML
python src/mapforce/schema/check_schema.py data/4_translated_mapforce/fda_medicines.xml

# Run the 92 UDF unit tests and dataset coverage audit
python src/mapforce/helpers/udf_reference.py
```
