# MapForce Helper Functions & Lookups

This directory provides reusable helper functions and lookup tables to standardize pharmaceutical attributes across **Drugs@FDA**, **Health Canada DPD**, and **EMA Medicines** into the shared target schema [medicines.xsd](../schema/medicines.xsd).

For normal execution, open [dpd_mapping.mfd](../dpd_mapping.mfd) or [ema_mapping.mfd](../ema_mapping.mfd). Both already import the two repository libraries below using relative paths. Functions should appear automatically in MapForce's Libraries pane; they are not installed in a developer's private library. Keep the repository folder structure intact. See the [team quick start](../README.md#team-quick-start) for inputs, outputs, and prerequisites.

---

## 1. Directory Contents

| File | Purpose |
| :--- | :--- |
| [wdi_helpers.mfd](wdi_helpers.mfd) | Built-in engine library with 14 low-level UDFs, including embedded `value-map` lookups. |
| [wdi_mapping_functions.mfd](wdi_mapping_functions.mfd) | Ten readable mapping functions; imports `wdi_helpers.mfd` from the same directory. |
| [build_helpers_mfd.py](build_helpers_mfd.py) | Generator and `.mfd` graph simulator for the low-level library and its 124 test cases. |
| [build_mapping_functions.py](build_mapping_functions.py) | Generator for the named-function library; optionally rebuilds both main diagrams. Development use only. |
| [wdi_helpers.xslt](wdi_helpers.xslt) | Companion XSLT 2.0 / 3.0 library; not required by the Built-in EMA/DPD mappings. |
| [udf_reference.py](udf_reference.py) | Python reference implementation, 124 helper test cases, and data coverage audits. |
| [udf_test_cases.csv](udf_test_cases.csv) | Shared helper test cases covering functions and edge cases across FDA, EMA, and DPD. |

Lookup XML files are located in [../lookups/](../lookups/):
* `regulatory_status.xml`: 25 entries mapping all FDA, EMA, and DPD statuses to 6 harmonized values.
* `product_class.xml`: Maps source classes to `Human`, `Veterinary`, or `Disinfectant`.
* `dosage_form.xml`: 227 entries mapping observed FDA and DPD forms to standard dosage forms.
* `route.xml`: 147 entries mapping observed routes to standard title-cased administration routes.
* `strength_unit.xml`: 202 entries mapping raw unit tokens to clean standard unit strings.
* `lookup.xsd`: XML Schema ensuring valid lookup syntax.

---

## 2. Function Reference

### 2.0 Named Mapping Functions (`wdi_mapping_functions.mfd`)

| Function | Purpose |
| :--- | :--- |
| `makeMedicineId(source, key)` | Join source, underscore, and the source entity key. |
| `getActiveSubstances(primary, fallback, separator)` | Normalize XML whitespace, prefer nonblank primary text over fallback, and split the selected text using the source separator. |
| `yesNoToBoolean(value)` | Compare a present value with `Yes`; emit true on a match, otherwise false. |
| `parseAuthorisationDate(value)` | Parse EMA DD/MM/YYYY dates into ISO dates. |
| `splitStrengths(values)` | Split a DPD strength list on `; `; does not itself validate or extract numeric values. |
| `standardizeRegulatoryStatus(raw)` | Readable wrapper around `stdRegulatoryStatus`. |
| `standardizeProductClass(raw)` | Readable wrapper around `stdProductClass`. |
| `standardizeAtcCodes(codes, additionalCodes)` | Combine human/veterinary lists, then standardize ATC codes. |
| `standardizeDosageForms(raw)` | Readable wrapper around `dosageFormList`. |
| `standardizeRoutes(raw)` | Readable wrapper around `routeList`. |

The main DPD diagram calls the existing status/class/ATC/form/route helpers directly. Its strength pipeline keeps token validation, numeric/unit extraction, and row-level wrapper filtering visible. Both extractors consume the same retained token, preserving each value/unit pair. There is no structured-output `getValidStrengths` function or extra internal schema dependency. The main EMA diagram uses the named wrappers. Count parent contexts and row filters remain in the main diagrams.

Supply an explicit empty-string constant for an unused fallback or additional-code input when adding a call; leaving an optional connector unwired can cause a connection to be lost during inlining.

### 2.1 Strength Splitting

#### `strengthValue(raw: string) -> decimal?`
* **Purpose:** Extracts the numeric strength value. When an explicit liquid volume, rate, or dose quantity denominator is present (e.g. `25MG/5ML`), normalizes the concentration per single denominator unit ($25 \div 5 = 5$). Mass concentrations (e.g. `10MG/GM`) retain their numeric numerator (`10`). Combination products sharing the same dose unit (e.g. `600MG/90MG`) are NOT divided into ratios. Unsupported numeric ranges (e.g. `185–259 MBq`, `0.25-3 CI/GENERATOR`) and missing numerators (e.g. `N/A/1000ML`) are omitted to prevent data corruption.
* **Examples:**
  * `"10MG"` $\rightarrow$ `10`
  * `"650MG"` $\rightarrow$ `650`
  * `"0.05%"` $\rightarrow$ `0.05`
  * `"25MG/5ML"` $\rightarrow$ `5`
  * `"10MG/GM"` $\rightarrow$ `10`
  * `"12.7MG/FIBER"` $\rightarrow$ `12.7`
  * `"75 CU/vial"` $\rightarrow$ `75`
  * `"20,000 UNITS/ML"` $\rightarrow$ `20000`
  * `"80MG/4ML (20MG/ML)"` $\rightarrow$ `20`
  * `"0.6MG/HR **Federal Register..."` $\rightarrow$ `0.6`
  * `"600MG/90MG"` $\rightarrow$ `600` (fixed-dose combination solid; not divided)
  * `"185–259 MBq"` $\rightarrow$ `()` (unsupported range; omitted)
  * `"N/A/1000ML"` $\rightarrow$ `()` (missing numerator; omitted)

#### `strengthUnit(raw: string) -> string?`
* **Purpose:** Extracts and normalizes the strength unit using `lookups/strength_unit.xml`.
* **Examples:**
  * `"10MG"` $\rightarrow$ `"mg"`
  * `"650MG"` $\rightarrow$ `"mg"`
  * `"0.05%"` $\rightarrow$ `"%"`
  * `"25MG/5ML"` $\rightarrow$ `"mg/mL"`
  * `"10MG/GM"` $\rightarrow$ `"mg/g"`
  * `"12.7MG/FIBER"` $\rightarrow$ `"mg/fiber"`
  * `"75 CU/vial"` $\rightarrow$ `"CU/vial"` (Clinical Units; not Curie)
  * `"20,000 UNITS/ML"` $\rightarrow$ `"U/mL"`
  * `"EQ 2GM BASE/VIAL"` $\rightarrow$ `"g/vial"`
  * `"0.2055MG/SPRAY"` $\rightarrow$ `"mg/spray"`
  * `"600MG/90MG"` $\rightarrow$ `"mg"` (retains primary mass unit; not "mg/mg")

> [!NOTE]
> **Implementation Architecture:** Both `strengthValue` and `strengthUnit` use pre-computed `value-map` lookup tables covering all 10,346 distinct strength tokens across EMA, Drugs@FDA, and Health Canada DPD, plus synthesized patterns (1–1000 with units and common decimals). This avoids runtime empty sequence propagation and engine-specific XPath function mismatches in MapForce Built-in.
> For combination drugs where a slash separates two active ingredient strengths (e.g., FDA `600MG/90MG`), mappers should replace `/` with `;` (`600MG; 90MG`) in pre-consolidation so that `tokenize(..., ';')` creates a separate `<strength>` element for each active substance.

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

### Existing EMA/DPD mappings

Open the main `.mfd` directly and select the Built-in engine. The saved imports load both libraries automatically. No generator, Python runtime, C++ compiler, personal library installation, or manual reconnection is required. The files were tested in MapForce 2027; older-version compatibility is unverified.

### Method A: Import into a new mapping

These steps are for creating a new mapping, not for running the existing EMA/DPD diagrams.

1. In MapForce, open the new mapping.
2. Go to **Component** $\rightarrow$ **Import MapForce Function Library...** (or **Import XSLT 2.0 / XQuery Function Library...** if using XSLT mode).
3. Select [wdi_helpers.mfd](wdi_helpers.mfd) and, for the named functions, [wdi_mapping_functions.mfd](wdi_mapping_functions.mfd). Save imports as relative paths. Use [wdi_helpers.xslt](wdi_helpers.xslt) only for the alternative XSLT workflow.
4. The helper functions will appear in the **Libraries** window.
5. Drag functions onto the canvas between source fields and the target [medicines.xsd](../schema/medicines.xsd) elements.

### Method B: Connecting XML Lookup Files Directly on the Canvas
If designing visually with MapForce core components:
1. Insert the lookup XML via **Component** $\rightarrow$ **Insert XML/Schema...** $\rightarrow$ select e.g. `lookups/dosage_form.xml`.
2. Connect `source_value` $\rightarrow$ `cleanText` $\rightarrow$ input 1 of `core | equal`.
3. Connect `lookup/entry/@raw` $\rightarrow$ input 2 of `core | equal`.
4. Connect `lookup/entry` and the boolean result of `equal` to `core | filter`.
5. Connect `filter/result/@std` $\rightarrow$ target element.
