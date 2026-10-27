# Web Data Integration: Pharmaceutical Drug Data

This repository contains the codebase, data pipeline, and documentation for our Web Data Integration (WDI) student project at the University of Mannheim. We are building an integrated dataset of approved pharmaceutical drugs across the **United States, the European Union, and Canada**, modelling a **medicine** (`brandName` + `activeSubstances`) as the central entity.

## Datasets
1. **Drugs@FDA (`01_us_drugs_at_fda`):** Official U.S. FDA database of approved drug products (`TXT/TSV` relational tables joined on `ApplNo` and `ProductNo`).
2. **EMA Medicines (`02_eu_ema_medicines`):** European Medicines Agency register of EU-authorised medicines (`XLSX/CSV`).
3. **Health Canada DPD (`03_ca_health_canada_dpd`):** Canadian Drug Product Database covering marketed, inactive, approved, and dormant drug products (`TXT/CSV`, 12 relational tables linked via `DRUG_CODE`).

## Project Phases
* **Phase I: Data Selection and Translation:** Profiling raw data, consolidating multiple contributing product records into normalized medicine entities using shared aggregation rules (plurality sponsor voting, hierarchical status resolution, and documented boolean policies — see [`src/mapforce/README.md`](src/mapforce/README.md#entity-consolidation-rules-pre-mapping-aggregations)), and mapping all three sources to the integrated target schema (`medicines.xsd` / `medicines.schema.json`) using Altova MapForce.
* **Phase II: Identity Resolution:** Identifying overlapping medicines across the three jurisdictions using blocking and similarity measures over `brandName` and `activeSubstances` via the PyDI framework (handling USAN vs. INN nomenclature, biologic suffixes, and salt forms).
* **Phase III: Data Fusion:** Merging matched records and resolving data conflicts across sources to produce a single, consolidated golden record per medicine.

## Local Setup
Ensure you have Python installed, then install the necessary dependencies for data profiling and integration:
```bash
pip install -r requirements.txt
```

## Repository Structure
```text
wdi-drug-integration/
├── data/
│   ├── 1_raw/                               # Original raw files from official regulators
│   │   ├── 01_us_drugs_at_fda/              # Core FDA tables (Products, Applications, Submissions, MarketingStatus)
│   │   ├── 02_eu_ema_medicines/             # EMA medicines register (ema_medicines.csv)
│   │   ├── 03_ca_health_canada_dpd/         # DPD tables split by status (marketed, inactive, approved, dormant)
│   │   └── _archives/                       # Compressed backups and deprecated v1 datasets
│   ├── 2_processed/                         # Pre-joined single-table CSVs (e.g., dpd_medicines.csv) ready for MapForce
│   ├── 3_profiling/                         # Overlap estimation (entity_count) & LLM-cleaned ingredient lists
│   ├── 4_translated_mapforce/               # Phase I outputs: XML/JSON files mapped to the integrated schema
│   └── 5_fused/                             # Phase III outputs: Final fused dataset after PyDI resolution & fusion
├── src/
│   ├── data_collection/                     # Python scripts for dataset consolidation, profiling, and overlap checks
│   ├── mapforce/                            # Altova MapForce mapping files (.mfd) and target schema (.xsd/.json)
│   ├── identity_resolution/                 # PyDI scripts for blocking and similarity measures
│   └── data_fusion/                         # PyDI scripts for conflict resolution and evaluation
├── docs/
│   ├── outline/                             # The 4-page project outline (LaTeX & PDF)
│   └── final_report/                        # Springer CS LaTeX files and final 12-page report
├── .gitignore                               # Excludes large raw data files while keeping .gitkeep folder structure
├── requirements.txt                         # Python dependencies
└── README.md                                # Project overview
```