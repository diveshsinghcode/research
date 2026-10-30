#!/usr/bin/env python3
"""Reproduce ERA synthetic dataset structure, formula, and weight-sensitivity audits.
No human annotations or external model outputs are generated or assumed.
Usage: python era_reproducibility_audit.py ERA_Pilot_Dataset_100_Cases_QC_Corrected.xlsx --outdir results
Dependencies: pandas, openpyxl, numpy, scipy
"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('workbook'); ap.add_argument('--outdir',default='era_results'); args=ap.parse_args()
    out=Path(args.outdir); out.mkdir(parents=True,exist_ok=True)
    df=pd.read_excel(args.workbook,sheet_name='100_Cases_QC_Corrected')
    ann=pd.read_excel(args.workbook,sheet_name='Original_Annotation_Form')
    required=['case_id','role','case_pattern','EC','ER','CA','CP','ET','illustrative_ERA','annotation_status']
    missing=[c for c in required if c not in df.columns]
    if missing: raise ValueError(f'Missing columns: {missing}')
    formula=.25*df.EC+.25*df.ER+.25*df.CA+.15*df.ET+.10*(1-df.CP)
    diff=(formula-df.illustrative_ERA).abs()
    X=np.column_stack([df.EC,df.ER,df.CA,df.ET,1-df.CP]).astype(float)
    w0=np.array([.25,.25,.25,.15,.10]); base=X@w0
    schemes={'Proposed':w0,'Equal':np.array([.2]*5),'Evidence-heavy':np.array([.30,.30,.15,.15,.10]),'Traceability-heavy':np.array([.20,.20,.20,.25,.15])}
    named=[]
    for name,w in schemes.items():
        s=X@w; named.append({'weight_scheme':name,'weights':w.tolist(),'mean_composite':float(s.mean()),'spearman_rho_vs_proposed':float(spearmanr(base,s).statistic)})
    rng=np.random.default_rng(20261027); mc=[]
    for name,alpha in [('Local Dirichlet(40 × proposed weights)',40*w0),('Broad Dirichlet(1,1,1,1,1)',np.ones(5))]:
        rhos=[]
        for _ in range(10000): rhos.append(float(spearmanr(base,X@rng.dirichlet(alpha)).statistic))
        rhos=np.asarray(rhos); mc.append({'scheme':name,'draws':10000,'seed':20261027,'rho_p05':float(np.quantile(rhos,.05)),'rho_median':float(np.quantile(rhos,.5)),'rho_p95':float(np.quantile(rhos,.95)),'share_rho_ge_0_90':float(np.mean(rhos>=.90))})
    pd.DataFrame(named).to_csv(out/'weight_sensitivity_named.csv',index=False); pd.DataFrame(mc).to_csv(out/'weight_sensitivity_monte_carlo.csv',index=False)
    anncols=['evidence_relevant_1to5','evidence_validity_1to5','benchmark_criterion_rating_1to5','contradiction_present_yes_no']
    status=df.annotation_status.astype(str).str.contains('requires human annotation/adjudication',case=False,na=False)
    result={'case_count':int(len(df)),'unique_case_ids':int(df.case_id.nunique()),'duplicate_case_ids':int(df.case_id.duplicated().sum()),'role_count':int(df.role.nunique()),'cases_per_role':{str(k):int(v) for k,v in df.role.value_counts().sort_index().items()},'case_pattern_counts':{str(k):int(v) for k,v in df.case_pattern.value_counts().sort_index().items()},'annotation_rows':int(len(ann)),'annotation_rows_with_any_core_field_filled':int(ann[anncols].notna().any(axis=1).sum()),'provisional_benchmark_cases':int(status.sum()),'formula_max_abs_difference':float(diff.max()),'formula_mean_abs_difference':float(diff.mean()),'formula_rows_abs_diff_gt_0_001':int((diff>.001).sum()),'stored_ERA_mean_descriptive_only':float(df.illustrative_ERA.mean()),'stored_ERA_min':float(df.illustrative_ERA.min()),'stored_ERA_max':float(df.illustrative_ERA.max()),'sensitivity_named':named,'sensitivity_monte_carlo':mc,'interpretation':'Synthetic/provisional data only. No AI accuracy, human agreement, employee-performance validity, fairness, or real-world effectiveness is estimated.'}
    (out/'audit_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
