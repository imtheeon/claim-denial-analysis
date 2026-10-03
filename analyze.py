import duckdb, glob, os
import pandas as pd
from scipy.stats import chi2_contingency

os.makedirs('outputs', exist_ok=True)
r = {}
for f in sorted(glob.glob('sql/[01][0-9]_*.sql')):
    if f.endswith('00_clean.sql'):
        continue
    stem = os.path.basename(f)[:-4]
    r[stem] = duckdb.sql(open(f, encoding='utf-8').read()).df()
    r[stem].to_csv(f'outputs/{stem}.csv', index=False)
    print(f'\n== {stem}\n{r[stem].to_string(index=False)}')
assert r['02_by_payer'].denied.sum() == r['01_kpis'].denied[0]

# segment x denied independence; Cramer's V = effect size (p is tiny at large n)
rows = []
for col in ['payer_type', 'provider_specialty', 'dx_chapter']:
    t = duckdb.sql(f"SELECT {col}, is_denied, count(*) n FROM 'data/clean/claims.parquet' WHERE is_adjudicated GROUP BY ALL").df().pivot(index=col, columns='is_denied', values='n').fillna(0)
    chi2, p, dof, _ = chi2_contingency(t)
    rows.append({'dimension': col, 'chi2': chi2, 'dof': dof, 'p': p, 'cramers_v': (chi2 / (t.values.sum() * (min(t.shape) - 1))) ** .5})
s = pd.DataFrame(rows)
s.to_csv('outputs/stats.csv', index=False)
print('\n== stats\n', s.to_string(index=False))
