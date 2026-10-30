#!/usr/bin/env python3
"""Regenerate ERA synthetic components so they follow the designed case patterns,
then test whether ERA (and simple flags) separate those planted patterns.

IMPORTANT: this is a CIRCULAR sensitivity check. The data are built to contain the
defects, so separation shows only that the formula REACTS to planted defects. It is
not validation of ERA, of any AI system, or of human agreement.

Usage:
  python era_planted_defects_generator.py ERA_Pilot_Dataset_100_Cases_QC_Corrected.xlsx --outdir planted_results [--seed 20261031]
Dependencies: pandas, numpy, scipy, openpyxl
"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import kruskal, mannwhitneyu

W = np.array([.25, .25, .25, .15, .10])
EC_FLAG, CP_FLAG = 0.70, 0.50      # pre-set flag thresholds (not tuned on results)
ERA_REVIEW = 0.70                  # composite-only review threshold for comparison

# pattern -> (lo, hi) uniform ranges; ER/ET/CP are drawn directly, EC and CA are
# derived from counts / ratings exactly as in the original workbook definitions.
RULES = {
    'aligned':              dict(ER=(.70, .90), ET=(.70, .90), CP=(.00, .15), ec_frac=(.80, 1.0), gap=(.00, .40)),
    'strong':               dict(ER=(.80, .98), ET=(.80, .98), CP=(.00, .10), ec_frac=(.85, 1.0), gap=(.00, .40)),
    'weak':                 dict(ER=(.40, .60), ET=(.60, .80), CP=(.05, .25), ec_frac=(.80, 1.0), gap=(.80, 1.50)),
    'mixed':                dict(ER=(.55, .75), ET=(.55, .80), CP=(.15, .40), ec_frac=(.60, .85), gap=(.40, .90)),
    'contradiction':        dict(ER=(.65, .90), ET=(.65, .90), CP=(.55, .90), ec_frac=(.80, 1.0), gap=(.00, .50)),
    'missing':              dict(ER=(.60, .85), ET=(.60, .85), CP=(.00, .15), ec_frac=(.20, .50), gap=(.00, .50)),
    'ai_human_agree_wrong': dict(ER=(.65, .90), ET=(.65, .90), CP=(.00, .15), ec_frac=(.80, 1.0), gap=(1.20, 2.00)),
}

def regenerate(df, seed):
    rng = np.random.default_rng(seed)
    out = df.copy()
    for i, r in df.iterrows():
        p = RULES[r.case_pattern]
        avail = int(r.evidence_available)
        considered = int(np.clip(round(avail * rng.uniform(*p['ec_frac'])), 1, avail))
        bench = float(r.independent_benchmark_score_1to5)
        gap = rng.uniform(*p['gap'])
        sign = rng.choice([-1, 1])
        ai = bench + sign * gap
        if not 1 <= ai <= 5:                       # flip direction if out of scale
            ai = bench - sign * gap
        ai = float(np.clip(ai, 1, 5))
        # agree_wrong: manager rating is set to the AI rating (+/-0.1) by design
        if r.case_pattern == 'ai_human_agree_wrong':
            mgr = float(np.clip(ai + rng.uniform(-.1, .1), 1, 5))
        else:
            mgr = float(r.historical_manager_rating_1to5)
        EC = considered / avail
        CA = max(0.0, 1 - abs(ai - bench) / 4)
        out.loc[i, ['evidence_considered_by_illustrative_ai']] = considered
        out.loc[i, 'illustrative_ai_rating_1to5'] = round(ai, 2)
        out.loc[i, 'historical_manager_rating_1to5'] = round(mgr, 2)
        out.loc[i, 'EC'] = round(EC, 3)
        out.loc[i, 'CA'] = round(CA, 3)
        for c in ['ER', 'ET', 'CP']:
            out.loc[i, c] = round(rng.uniform(*p[c]), 3)
    out['planted_ERA'] = (W[0]*out.EC + W[1]*out.ER + W[2]*out.CA + W[3]*out.ET + W[4]*(1-out.CP)).round(4)
    out['rating_gap_to_benchmark'] = (out.illustrative_ai_rating_1to5 - out.independent_benchmark_score_1to5).abs().round(3)
    out['flag_low_EC'] = out.EC < EC_FLAG
    out['flag_high_CP'] = out.CP > CP_FLAG
    out['flag_any'] = out.flag_low_EC | out.flag_high_CP
    return out

def auc(pos, neg):
    """P(score_pos > score_neg) with ties=0.5 (Mann-Whitney AUC)."""
    u = mannwhitneyu(pos, neg, alternative='two-sided').statistic
    return float(u / (len(pos) * len(neg)))

def evaluate(d):
    res = {}
    groups = [g.planted_ERA.values for _, g in d.groupby('case_pattern')]
    res['kruskal_ERA_by_pattern_p'] = float(kruskal(*groups).pvalue)
    res['pattern_means'] = d.groupby('case_pattern')[['EC', 'ER', 'CA', 'CP', 'ET', 'planted_ERA']].mean().round(3).to_dict('index')
    res['pattern_ranges_ERA'] = {k: [float(g.min()), float(g.max())] for k, g in d.groupby('case_pattern').planted_ERA}
    # Detection of planted defects: composite alone vs component flags
    tasks = {
        'contradiction': ('CP', d.case_pattern == 'contradiction', 'flag_high_CP'),
        'missing':       ('EC', d.case_pattern == 'missing',       'flag_low_EC'),
    }
    det = {}
    for name, (comp, mask, flag) in tasks.items():
        pos_era, neg_era = d.loc[mask, 'planted_ERA'], d.loc[~mask, 'planted_ERA']
        row = {'n_planted': int(mask.sum()),
               'AUC_low_ERA_detects': round(auc(neg_era.values, pos_era.values), 3),  # P(ERA_other > ERA_planted)
               'flag_recall': round(float(d.loc[mask, flag].mean()), 3),
               'flag_precision': round(float(d.loc[d[flag], 'case_pattern'].eq(name).mean()) if d[flag].any() else float('nan'), 3),
               'flag_false_positive_rate': round(float(d.loc[~mask, flag].mean()), 3)}
        rev = d.planted_ERA < ERA_REVIEW
        row['ERA<%.2f_recall' % ERA_REVIEW] = round(float(rev[mask].mean()), 3)
        row['ERA<%.2f_false_positive_rate' % ERA_REVIEW] = round(float(rev[~mask].mean()), 3)
        det[name] = row
    # Weak and agree_wrong: composite-level separation vs aligned/strong
    for name in ['weak', 'ai_human_agree_wrong']:
        mask = d.case_pattern == name
        ref = d.case_pattern.isin(['aligned', 'strong'])
        det[name] = {'n_planted': int(mask.sum()),
                     'AUC_low_ERA_vs_aligned_strong': round(auc(d.loc[ref, 'planted_ERA'].values, d.loc[mask, 'planted_ERA'].values), 3)}
    # Agreement-is-not-validity check: manager-AI agreement vs benchmark gap
    m = d.case_pattern == 'ai_human_agree_wrong'
    det['agree_wrong_manager_AI_gap_mean'] = round(float((d.loc[m, 'illustrative_ai_rating_1to5'] - d.loc[m, 'historical_manager_rating_1to5']).abs().mean()), 3)
    det['agree_wrong_benchmark_gap_mean'] = round(float(d.loc[m, 'rating_gap_to_benchmark'].mean()), 3)
    res['detection'] = det
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('workbook'); ap.add_argument('--outdir', default='planted_results')
    ap.add_argument('--seed', type=int, default=20261031); ap.add_argument('--replicates', type=int, default=200)
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(a.workbook, sheet_name='100_Cases_QC_Corrected')
    planted = regenerate(df, a.seed)
    res = evaluate(planted)
    # Replicate over seeds to show the result is not a one-draw artefact
    reps = {k: [] for k in ['contradiction_AUC', 'missing_AUC', 'weak_AUC', 'agree_wrong_AUC', 'contradiction_flag_recall', 'missing_flag_recall']}
    for s in range(a.replicates):
        r = evaluate(regenerate(df, a.seed + 1 + s))['detection']
        reps['contradiction_AUC'].append(r['contradiction']['AUC_low_ERA_detects']); reps['missing_AUC'].append(r['missing']['AUC_low_ERA_detects'])
        reps['weak_AUC'].append(r['weak']['AUC_low_ERA_vs_aligned_strong']); reps['agree_wrong_AUC'].append(r['ai_human_agree_wrong']['AUC_low_ERA_vs_aligned_strong'])
        reps['contradiction_flag_recall'].append(r['contradiction']['flag_recall']); reps['missing_flag_recall'].append(r['missing']['flag_recall'])
    res['replicates'] = {k: {'n': a.replicates, 'p05': round(float(np.quantile(v, .05)), 3), 'median': round(float(np.median(v)), 3), 'p95': round(float(np.quantile(v, .95)), 3)} for k, v in reps.items()}
    res['seed'] = a.seed
    res['thresholds'] = {'EC_flag_below': EC_FLAG, 'CP_flag_above': CP_FLAG, 'ERA_review_below': ERA_REVIEW}
    res['interpretation'] = ('CIRCULAR sensitivity check: components were generated to follow the designed patterns. '
                             'Results show ERA and flags react to planted defects; they are not validation, accuracy, human agreement, fairness, or real-world effectiveness.')
    with pd.ExcelWriter(out / 'ERA_Pilot_Dataset_100_Cases_Planted_Components.xlsx') as xw:
        planted.drop(columns=['evidence_items_original_raw']).to_excel(xw, sheet_name='100_Cases_Planted', index=False)
        pd.DataFrame([{'rule_pattern': k, **{kk: str(vv) for kk, vv in v.items()}} for k, v in RULES.items()]).to_excel(xw, sheet_name='Generation_Rules', index=False)
    (out / 'planted_defects_summary.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    print(json.dumps(res, indent=2))

if __name__ == '__main__':
    main()
