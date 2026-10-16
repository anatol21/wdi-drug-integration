# MapForce Helper Functions & Lookups

This directory provides reusable helper functions and lookup tables to standardize pharmaceutical attributes across **Drugs@FDA**, **Health Canada DPD**, and **EMA Medicines** into the shared target schema [`medicines.xsd`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/schema/medicines.xsd).

---

## 1. Directory Contents

| File | Purpose |
| :--- | :--- |
| [`wdi_helpers.mfd`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/helpers/wdi_helpers.mfd) | Altova MapForce User-Defined Function (UDF) library for the **Built-in** execution engine. |
| [`wdi_helpers.xslt`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/helpers/wdi_helpers.xslt) | Companion **XSLT 2.0 / 3.0** library, directly importable via `Component | Import XSLT 2.0 / XQuery Function Library...`. |
| [`udf_reference.py`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/helpers/udf_reference.py) | Python reference implementation and oracle test suite running 92 unit tests and data coverage audits. |
| [`udf_test_cases.csv`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/helpers/udf_test_cases.csv) | Test suite (92 test cases) covering all functions and edge cases across FDA and DPD data. |

Lookup XML files are located in [`../lookups/`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/lookups/):
* `regulatory_status.xml`: 25 entries mapping all FDA, EMA, and DPD statuses to 6 harmonized values.
* `product_class.xml`: Maps source classes to `Human`, `Veterinary`, or `Disinfectant`.
* `dosage_form.xml`: 227 entries mapping observed FDA and DPD forms to standard dosage forms.
* `route.xml`: 147 entries mapping observed routes to standard title-cased administration routes.
* `strength_unit.xml`: 202 entries mapping raw unit tokens to clean standard unit strings.
* `lookup.xsd`: XML Schema ensuring valid lookup syntax.

---

## 2. Function Reference

### 2.1 Strength Splitting

#### `strengthValue(raw: string) -> decimal?`
* **Purpose:** Extracts the numeric strength value. When an explicit volume/quantity denominator is present (e.g. `25MG/5ML`), normalizes the concentration per single denominator unit ($25 \div 5 = 5$).
* **Examples:**
  * `"10MG"` $\rightarrow$ `10`
  * `"0.05%"` $\rightarrow$ `0.05`
  * `"25MG/5ML"` $\rightarrow$ `5`
  * `"20,000 UNITS/ML"` $\rightarrow$ `20000`
  * `"80MG/4ML (20MG/ML)"` $\rightarrow$ `20`
  * `"0.6MG/HR **Federal Register..."` $\rightarrow$ `0.6`

#### `strengthUnit(raw: string) -> string?`
* **Purpose:** Extracts and normalizes the strength unit using `lookups/strength_unit.xml`.
* **Examples:**
  * `"10MG"` $\rightarrow$ `"mg"`
  * `"0.05%"` $\rightarrow$ `"%"`
  * `"25MG/5ML"` $\rightarrow$ `"mg/mL"`
  * `"20,000 UNITS/ML"` $\rightarrow$ `"U/mL"`
  * `"EQ 2GM BASE/VIAL"` $\rightarrow$ `"g/vial"`
  * `"0.2055MG/SPRAY"` $\rightarrow$ `"mg/spray"`

---

### 2.2 Regulatory Status Standardization

#### `stdRegulatoryStatus(raw: string) -> string?`
* **Controlled Target Vocabulary:** `Authorised`, `Suspended`, `Pending`, `Withdrawn`, `Application withdrawn`, `Refused`.
* **Examples:**
  * FDA: `"Prescription"` $\rightarrow$ `"Authorised"`, `"Over-the-counter"` $\rightarrow$ `"Authorised"`, `"Discontinued"` $\rightarrow$ `"Withdrawn"`
  * EMA: `"Authorised"` $\rightarrow$ `"Authorised"`, `"Opinion"` $\rightarrow$ `"Pending"`, `"Withdrawn"` $\rightarrow$ `"Withdrawn"`, `"Refused"` $\rightarrow$ `"Refused"`
  * DPD: `"MARKETED"` $\rightarrow$ `"Authorised"`, `"APPROVED"` $\rightarrow$ `"Authorised"`, `"DORMANT"` $\rightarrow$ `"Authorised"`, `"CANCELLED POST MARKET"` $\rightarrow$ `"Withdrawn"`, `"CANCELLED PRE MARKET"` $\rightarrow$ `"Application withdrawn"`

#### `bestRegulatoryStatus(list: string) -> string?`
* **Purpose:** For products with multiple historical statuses (e.g. DPD `"MARKETED; CANCELLED POST MARKET"`), picks the most active / favourable status according to the hierarchy:
  $$\text{Authorised} > \text{Suspended} > \text{Pending} > \text{Withdrawn} > \text{Application withdrawn} > \text{Refused}$$

---

### 2.3 Product Class Standardization

#### `stdProductClass(raw: string) -> string?`
* **Controlled Target Vocabulary:** `Human`, `Veterinary`, `Disinfectant`.
* **Examples:**
  * DPD: `"Human"` $\rightarrow$ `"Human"`, `"Veterinary"` $\rightarrow$ `"Veterinary"`, `"Disinfectant"` $\rightarrow$ `"Disinfectant"`, `"Radiopharmaceutical"` $\rightarrow$ `"Human"`.
  * FDA: FDA Applications are derived by passing `ApplType` (`"NDA"`, `"ANDA"`, `"BLA"` $\rightarrow$ `"Human"`).

---

### 2.4 Dosage Form Standardization

#### `stdDosageForm(raw: string) -> string?`
* **Purpose:** Standardizes a single dosage form string using `lookups/dosage_form.xml`.
* **Examples:**
  * `"TABLET"` $\rightarrow$ `"Tablet"`
  * `"TABLET, EXTENDED RELEASE"` $\rightarrow$ `"Tablet, extended-release"`
  * `"CAPSULE"` $\rightarrow$ `"Capsule"`
  * `"INJECTABLE"` $\rightarrow$ `"Injection"`
  * `"UNKNOWN"` $\rightarrow$ `()` (omitted in target output)

#### `dosageFormList(list: string) -> string?`
* **Purpose:** For multi-form products (e.g. DPD `"SOLUTION; LIQUID"`), translates each item, deduplicates identical forms, sorts alphabetically, and joins with `"; "` $\rightarrow$ `"Liquid; Solution"`.

---

### 2.5 Route Standardization

#### `stdRoute(raw: string) -> string?`
* **Purpose:** Standardizes a single administration route using `lookups/route.xml`.
* **Examples:**
  * `"ORAL"` $\rightarrow$ `"Oral"`
  * `"INTRAVENOUS"` $\rightarrow$ `"Intravenous"`
  * `"DISINFECTANT (Hospital/HC Facilities)"` $\rightarrow$ `"Disinfectant"`
  * `"UNKNOWN"` $\rightarrow$ `()` (omitted in target output)

#### `routeList(list: string) -> string?`
* **Purpose:** For multi-route products (e.g. DPD `"SUBCUTANEOUS; INTRAMUSCULAR; INTRAVENOUS; INTRAVENOUS"`), translates each item, deduplicates, sorts alphabetically, and joins with `"; "` $\rightarrow$ `"Intramuscular; Intravenous; Subcutaneous"`.

---

### 2.6 FDA Form Decomposition

#### `fdaFormPart(Form: string) -> string`
* In FDA `Products.txt`, `Form` combines dosage form and route separated by a semicolon (e.g. `"TABLET, EXTENDED RELEASE;ORAL"`).
* Returns the dosage form portion before `";"` $\rightarrow$ `"TABLET, EXTENDED RELEASE"`.

#### `fdaRoutePart(Form: string) -> string`
* Returns the route portion after `";"` $\rightarrow$ `"ORAL"`.

---

### 2.7 ATC Code Standardization

#### `stdAtcCode(raw: string) -> string?`
* **Purpose:** Cleans single or semicolon-separated WHO ATC / veterinary ATCvet codes so 100% of EMA and DPD records validate against `AtcCodeType` in `medicines.xsd`:
  * Strips trailing asterisks (e.g. DPD `"L04AA40*"` $\rightarrow$ `"L04AA40"`, ensuring exact match with EMA for *Mavenclad*).
  * Drops unassigned placeholders (`"Not yet assigned"` in EMA, `"UNASSIGN"` in DPD) $\rightarrow$ `()` (element omitted).
  * Fixes EMA typo `"VO4D"` $\rightarrow$ `"V04D"`.
  * Deduplicates, sorts, and formats multi-code strings (e.g. `"A10AB04;A10AD04"` $\rightarrow$ `"A10AB04; A10AD04"`, or EMA human + vet `concat(ATC_human, ";", ATC_vet)` $\rightarrow$ `"QI09AA07"`).

---

## 3. How to Plug Them into Altova MapForce

### Method A: Import as Function Library (Recommended)
1. In MapForce, open your mapping (`fda_mapping.mfd` or `dpd_mapping.mfd`).
2. Go to **Component** $\rightarrow$ **Import MapForce Function Library...** (or **Import XSLT 2.0 / XQuery Function Library...** if using XSLT mode).
3. Select [`wdi_helpers.mfd`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/helpers/wdi_helpers.mfd) or [`wdi_helpers.xslt`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/helpers/wdi_helpers.xslt).
4. The helper functions will appear in the **Libraries** window under `wdi_helpers`.
5. Drag and drop them directly onto the canvas between your source fields and the target [`medicines.xsd`](file:///Users/gabrielhimmelein/Projects/wdi-drug-integration/src/mapforce/schema/medicines.xsd) elements.

### Method B: Connecting XML Lookup Files Directly on the Canvas
If designing visually with MapForce core components:
1. Insert the lookup XML via **Component** $\rightarrow$ **Insert XML/Schema...** $\rightarrow$ select e.g. `lookups/dosage_form.xml`.
2. Connect `source_value` $\rightarrow$ `cleanText` $\rightarrow$ input 1 of `core | equal`.
3. Connect `lookup/entry/@raw` $\rightarrow$ input 2 of `core | equal`.
4. Connect `lookup/entry` and the boolean result of `equal` to `core | filter`.
5. Connect `filter/result/@std` $\rightarrow$ target element.
