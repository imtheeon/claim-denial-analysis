"""Static README charts (matplotlib) built only from outputs/*.csv."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ACCENT, GREY, GRID, TEXT = "#D55E00", "#9E9E9E", "#D9D9D9", "#4D4D4D"
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Inter", "Arial", "DejaVu Sans"],
                     "text.color": TEXT, "axes.labelcolor": TEXT, "xtick.color": TEXT, "ytick.color": TEXT,
                     "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 100})
rd = lambda n: pd.read_csv(f"outputs/{n}.csv")


def fig_(title, xlabel, ylabel, w=7, h=4):
    f, ax = plt.subplots(figsize=(w, h))
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color="#262626", pad=14)
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    return f, ax


def save(f, name, caption):
    f.text(0.01, 0.01, "So what: " + caption, fontsize=8.5, color=TEXT)
    f.tight_layout(rect=(0, 0.04, 1, 1))
    f.savefig(f"assets/{name}.png", dpi=150, facecolor="white"); plt.close(f)


def pct_bars(ax, x, r, colors, lo=None, hi=None, w=0.6, one=False):
    err = None if lo is None else [r - lo, hi - r]
    ax.bar(x, r, w, color=colors, yerr=err, ecolor=TEXT, error_kw={"lw": 1})
    for xi, v in zip(x, r):
        ax.text(xi, v + 0.04, f"{v:.1%}" if one or v < 0.1 else f"{v:.0%}", ha="center", fontsize=9)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.set_ylim(0, 1.15)


# 1. documentation bands
d = rd("08_drivers"); d = d[d.driver == "documentation_completeness"]
f, ax = fig_("81% of claims below 0.7 documentation are denied; above it, 1.7%", "Documentation completeness (score)", "Denial rate (%, 95% CI)")
labels = [s.split(": ")[1] for s in d.level]
pct_bars(ax, labels, d.denial_rate.values, [ACCENT, ACCENT, GREY, GREY], d.ci_low.values, d.ci_high.values)
ax.annotate("Cliff at 0.7", (2, 0.1), (2, 0.5), color=ACCENT, ha="center", arrowprops=dict(arrowstyle="->", color=ACCENT))
save(f, "doc_denial_rate", "hold claims below 0.7 for documentation review before filing.")

# 2. denied $ share, low vs adequate doc
m = rd("10_doc_auth_matrix"); a = m[m.part.str.startswith("A")].sort_values("share_of_claims", ascending=False)
f, ax = fig_("36% of claims carry 96% of denied dollars", "", "Share (%)")
x = np.arange(2)
ax.bar(x - 0.2, a.share_of_claims, 0.4, color=GRID)
ax.bar(x + 0.2, a.share_of_denied_usd, 0.4, color=[GREY, ACCENT])
for xi, v in zip(x - 0.2, a.share_of_claims): ax.text(xi, v + 0.02, f"{v:.0%}", ha="center", fontsize=9)
for xi, v in zip(x + 0.2, a.share_of_denied_usd): ax.text(xi, v + 0.02, f"{v:.0%}", ha="center", fontsize=9)
ax.set_xticks(x, ["Adequate doc (>=0.7)", "Low doc (<0.7)"]); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.set_ylim(0, 1.1)
save(f, "denied_dollar_share", "light bar = share of claims, dark bar = share of denied dollars.")

# 3. payers are flat
p = rd("02_by_payer").sort_values("denial_rate", ascending=False)
f, ax = fig_("Payers differ by under 1 point: not a payer problem", "Payer", "Denial rate (%, 95% CI)")
pct_bars(ax, p.payer_type.str.replace("_", " "), p.denial_rate.values, GREY, p.ci_low.values, p.ci_high.values, one=True)
ax.set_ylim(0, 0.5); ax.tick_params(axis="x", labelsize=7.5)
ax.axhline(0.3019, color=ACCENT, ls="--", lw=1); ax.text(5.4, 0.312, "Overall 30.2%", color=ACCENT, ha="right", fontsize=9)
save(f, "payer_flat", "escalating payer by payer would be misdirected; overlapping intervals.")

# 4. auth gap within documentation bands
b = m[m.part.str.startswith("B") & (m.auth_status.notna())]
f, ax = fig_("Within a documentation band, an auth gap adds about 11 points", "Documentation band (auth-required claims)", "Denial rate (%)")
bands = ["1: <0.5", "2: 0.5-0.7", "3: 0.7-0.9"]
for off, (st, c) in zip([-0.2, 0.2], [("gap", ACCENT), ("no gap", GREY)]):
    v = b[b.auth_status == st].set_index("doc_group").loc[bands, "denial_rate"]
    ax.bar(np.arange(3) + off, v, 0.4, color=c, label="Auth gap" if st == "gap" else "No auth gap")
    for xi, y in zip(np.arange(3) + off, v): ax.text(xi, y + 0.02, f"{y:.0%}" if y > .1 else f"{y:.1%}", ha="center", fontsize=9)
ax.set_xticks(range(3), [s.split(": ")[1] for s in bands]); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.set_ylim(0, 1.15)
ax.legend(frameon=False, loc="upper right", fontsize=8)
save(f, "auth_gap_by_doc", "fix documentation first; the auth effect is second-order.")

# 5. recoverable by category
c = rd("06_by_denial_category").assign(nr=lambda t: t.denied_usd - t.recoverable_usd).sort_values("denied_usd")
f, ax = fig_("Coding errors hold the most recoverable dollars", "Denied billed $ (millions)", "", h=4.2)
ax.barh(c.denial_category.str.replace("_", " "), c.recoverable_usd / 1e6, color=ACCENT, label="Recoverable (modeled)")
ax.barh(c.denial_category.str.replace("_", " "), c.nr / 1e6, left=c.recoverable_usd / 1e6, color=GREY, label="Not recoverable")
for i, (r, t) in enumerate(zip(c.recoverable_usd, c.denied_usd)): ax.text(t / 1e6 + 0.3, i, rf"\${r/1e6:.1f}M of \${t/1e6:.1f}M", va="center", fontsize=8)
ax.set_xlim(0, 27); ax.legend(frameon=False, loc="lower right", fontsize=8); ax.grid(axis="y", visible=False)
save(f, "recoverable_by_category", "work coding-error and bundling first; duplicates and late filings can only be prevented.")

# 6. quarterly trend
t = rd("07_trend_quarterly")
f, ax = fig_("Denial rate stays 29.3%-30.9% in every quarter", "Quarter", "Denial rate (%)")
ax.plot(t.year_quarter, t.denial_rate, color=GREY, marker="o", lw=2)
ax.scatter([t.denial_rate.idxmax()], [t.denial_rate.max()], color=ACCENT, zorder=3)
ax.annotate("Highest: 30.9%", (t.denial_rate.idxmax(), t.denial_rate.max()), (t.denial_rate.idxmax(), 0.40), color=ACCENT, ha="center", arrowprops=dict(arrowstyle="->", color=ACCENT))
ax.set_ylim(0, 0.6); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.tick_params(axis="x", rotation=60, labelsize=8)
save(f, "quarterly_trend", "no single quarter explains the problem, so waiting will not fix it.")
