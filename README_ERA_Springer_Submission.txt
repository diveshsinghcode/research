ERA Springer LNCS Submission Package - Updated 30 October 2026

Primary revised submission files:
- ERA_Springer_LNCS_Revised.pdf (10 pages; compiled twice with XeLaTeX)
- ERA_Springer_LNCS_Revised.tex (editable source)

Original source files:
- ERA_Springer_LNCS.pdf
- ERA_Springer_LNCS.tex

Reproducibility materials used by the current manuscript:
- ERA_Pilot_Dataset_100_Cases_QC_Corrected.xlsx (exact input workbook)
- era_reproducibility_audit.py (recomputes formula audit and sensitivity results)
- reproducibility_outputs/ERA_reproducibility_audit_summary.json
- reproducibility_outputs/ERA_case_level_recomputed_scores.csv
- reproducibility_outputs/local_dirichlet_40x_proposed.csv
- reproducibility_outputs/broad_dirichlet_ones.csv

Additional planted-defect materials:
- reproducibility_materials/era_planted_defects_generator.py
- reproducibility_materials/planted_defects_summary.json
- reproducibility_materials/ERA_Pilot_Dataset_100_Cases_Planted_Components.xlsx

Research scope and integrity:
- The manuscript is a framework specification and reproducible computational audit of synthetic data.
- No human annotations, human study outcomes, fresh LLM/API outputs, or real employee records are claimed.
- All 100 reference cases remain provisional; all 500 core criterion-level annotation rows remain uncompleted.
- Findings concern workbook structure, arithmetic consistency, and mathematical sensitivity under specified weight perturbations only.
- The planted-defect check is circular because components are generated to follow designed patterns; it is not validation.
- The paper does not claim AI accuracy, human agreement, fairness validation, explanation usefulness, or real-world effectiveness.

Reproduce the main audit from this folder:
python era_reproducibility_audit.py ERA_Pilot_Dataset_100_Cases_QC_Corrected.xlsx --outdir reproducibility_outputs

Dependencies: Python 3, numpy, scipy, openpyxl.

See FINAL_CONTENT_AUDIT.txt for audit findings and remaining author/conference checks. The audit is not a guarantee of acceptance or plagiarism clearance.
