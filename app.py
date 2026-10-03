import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ACCENT, GREY, GRID, TEXT = "#D55E00", "#9E9E9E", "#D9D9D9", "#4D4D4D"
st.set_page_config(page_title="Claim Denial Analysis", layout="wide")


@st.cache_data
def load():
    df = pd.read_parquet("data/clean/claims.parquet")
    df["claim_month"] = pd.to_datetime(df["claim_month"])
    df["doc_band"] = pd.cut(df["documentation_completeness"], [0, 0.5, 0.7, 0.9, 1.01],
                            right=False, labels=["<0.5", "0.5-0.7", "0.7-0.9", ">=0.9"])
    df["low_doc"] = df["documentation_completeness"] < 0.7
    return df


def rate(g, by):
    """Denial rate per group with a 95% Wilson interval (fractions)."""
    t = g.groupby(by, observed=True)["is_denied"].agg(k="sum", n="count").reset_index()
    p, n, z = t["k"] / t["n"], t["n"], 1.96
    mid = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return t.assign(rate=p, lo=mid - half, hi=mid + half)


def layout(fig, title, x, y, **kw):
    fig.update_layout(title=dict(text=title, font_size=16), font_family="Inter, Arial, sans-serif",
                      font_color=TEXT, plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", height=380,
                      margin=dict(t=70, b=40, l=10, r=10), legend_title_text="", bargap=0.35, **kw)
    fig.update_xaxes(title=x, gridcolor=GRID, zeroline=False)
    fig.update_yaxes(title=y, gridcolor=GRID, zeroline=False)
    return fig


def note(fig, x, y, text, **kw):
    fig.add_annotation(x=x, y=y, text=text, showarrow=True, arrowcolor=ACCENT, font_color=ACCENT, **kw)


def show(fig, so_what):
    st.plotly_chart(fig, width="stretch")
    st.caption("So what: " + so_what)


def err(r):
    return dict(type="data", symmetric=False, array=r["hi"] - r["rate"], arrayminus=r["rate"] - r["lo"],
                color=TEXT, thickness=1)


HOVER = "%{x}<br>Denial rate: %{y:.1%}<br>Claims: %{customdata:,}<extra></extra>"
df = load()
st.title("Claim denial analysis")
st.caption("Synthetic data (Kaggle DenialIQ, 120k claims, 2021-01 to 2024-06). Denial rate = denied / adjudicated.")
with st.container(border=True):
    st.markdown("**Bottom line (full dataset):** denials tie up **$74.1M** in billed charges over 42 months "
                "(30.2% of adjudicated claims) and are **not a payer, specialty or diagnosis problem**: every group sits "
                "at 29.5-32.1%. **96% of denied dollars come from the 36% of claims sent with documentation "
                "completeness below 0.7.** Hold those claims for documentation review, work coding-error and "
                "bundling denials first, and add a prior-auth check at scheduling.")

with st.sidebar:
    st.header("Filters")
    payer = st.multiselect("Payer", sorted(df["payer_type"].unique()))
    spec = st.multiselect("Specialty", sorted(df["provider_specialty"].unique()))
    dx = st.multiselect("Diagnosis chapter", sorted(df["dx_chapter"].unique()))
    months = sorted(df["claim_month"].dt.to_period("M").unique())
    lo, hi = st.select_slider("Claim month", months, value=(months[0], months[-1]),
                              format_func=lambda p: p.strftime("%b %Y"))

base = df[df["is_adjudicated"]]
f = base[base["claim_month"].dt.to_period("M").between(lo, hi)]
for col, sel in [("payer_type", payer), ("provider_specialty", spec), ("dx_chapter", dx)]:
    if sel:
        f = f[f[col].isin(sel)]
den = f[f["is_denied"]]
if den.empty:
    st.info("No rows match these filters.")
    st.stop()

overall = f["is_denied"].mean()
usd = den["claim_amount_usd"].sum()
low_share = den.loc[den["low_doc"], "claim_amount_usd"].sum() / usd
rec = den["estimated_recovery_usd"].sum()
k = st.columns(4)
k[0].metric("Denial rate", f"{overall:.1%}", f"{len(f):,} adjudicated claims", delta_color="off", delta_arrow="off")
k[1].metric("Denied $ (billed)", f"${usd / 1e6:,.1f}M", f"{len(den):,} denied claims", delta_color="off", delta_arrow="off")
k[2].metric("Denied $ from low-doc claims", f"{low_share:.0%}",
            f"vs {f['low_doc'].mean():.0%} of claims", delta_color="off", delta_arrow="off", help="Documentation completeness < 0.7")
k[3].metric("Recoverable $ (modeled)", f"${rec / 1e6:,.1f}M", f"{rec / usd:.0%} of denied $", delta_color="off", delta_arrow="off")
st.write("")

c1, c2 = st.columns(2, gap="large")
with c1:
    r = rate(f, "doc_band")
    low = r.loc[r["doc_band"].isin(["<0.5", "0.5-0.7"]), ["k", "n"]].sum()
    high = r.loc[r["doc_band"].isin(["0.7-0.9", ">=0.9"]), ["k", "n"]].sum()
    fig = go.Figure(go.Bar(x=r["doc_band"].astype(str), y=r["rate"], customdata=r["n"], hovertemplate=HOVER,
                           marker_color=[ACCENT if b in ("<0.5", "0.5-0.7") else GREY for b in r["doc_band"]],
                           text=r["rate"].map("{:.0%}".format), textposition="outside", error_y=err(r)))
    layout(fig, f"{low.k / max(low.n, 1):.0%} denied below 0.7 documentation vs {high.k / max(high.n, 1):.1%} above",
           "Documentation completeness (score)", "Denial rate (%)", yaxis=dict(tickformat=".0%", range=[0, 1.15]))
    note(fig, "0.7-0.9", 0.1, "Cliff at 0.7", ax=0, ay=-60)
    show(fig, "Denials collapse once documentation reaches 0.7; fix documentation before filing.")
with c2:
    g = f.assign(auth=f["auth_gap"].map({True: "Auth gap", False: "No auth gap"}),
                 docs=f["low_doc"].map({True: "Low doc (<0.7)", False: "High doc (>=0.7)"}))
    r = rate(g, ["docs", "auth"])
    fig = go.Figure()
    for a, c in [("Auth gap", ACCENT), ("No auth gap", GREY)]:
        s = r[r["auth"] == a]
        fig.add_bar(name=a, x=s["docs"], y=s["rate"], marker_color=c, customdata=s["n"], hovertemplate=HOVER,
                    text=s["rate"].map("{:.0%}".format), textposition="outside", error_y=err(s))
    layout(fig, "Documentation matters far more than a prior-auth gap",
           "Documentation group", "Denial rate (%)", barmode="group", yaxis=dict(tickformat=".0%", range=[0, 1.15]))
    show(fig, "Across the full dataset, an auth gap adds about 11 points within a documentation band, while "
              "documentation moves the rate by 60+ points: fix docs first.")

c3, c4 = st.columns(2, gap="large")
with c3:
    g = den.groupby("denial_category").agg(billed=("claim_amount_usd", "sum"), rec=("estimated_recovery_usd", "sum"))
    g["Not recoverable"] = g["billed"] - g["rec"]
    g = g.rename(columns={"rec": "Recoverable"}).sort_values("billed").drop(columns="billed")
    top = g["Recoverable"].idxmax()
    fig = go.Figure()
    for col, c in [("Recoverable", ACCENT), ("Not recoverable", GREY)]:
        fig.add_bar(name=col, y=g.index.str.replace("_", " "), x=g[col], orientation="h", marker_color=c,
                    text=g[col].map(lambda v: f"${v / 1e6:.1f}M" if v >= 2e6 else ""), textposition="inside",
                    hovertemplate="%{y}<br>" + col + ": %{x:$,.0f}<extra></extra>")
    layout(fig, f"{top.replace('_', ' ').capitalize()} holds the most recoverable $", "Denied billed $", "Denial category",
           barmode="stack", xaxis=dict(tickprefix="$", tickformat=",.2s", tickangle=0, nticks=5),
           legend=dict(orientation="h", y=1.12, x=0))
    note(fig, g.loc[top].sum(), top.replace("_", " "), "Work first", ax=50, ay=0)
    show(fig, "Work recoverable categories first; duplicate and timely-filing denials can only be prevented.")
with c4:
    dim = st.selectbox("Segment", ["payer_type", "provider_specialty", "dx_chapter"],
                       format_func=lambda c: {"payer_type": "Payer", "provider_specialty": "Specialty",
                                              "dx_chapter": "Diagnosis chapter"}[c])
    r = rate(f, dim).sort_values("rate")
    spread = r["rate"].max() - r["rate"].min()
    fig = go.Figure(go.Bar(y=r[dim], x=r["rate"], orientation="h", marker_color=GREY, customdata=r["n"],
                           error_x=err(r), text=r["rate"].map("{:.1%}".format), textposition="inside",
                           insidetextanchor="start", hovertemplate="%{y}<br>Denial rate: %{x:.1%}<br>Claims: %{customdata:,}<extra></extra>"))
    fig.add_vline(x=overall, line_dash="dash", line_color=ACCENT, annotation_text=f"Overall {overall:.1%}",
                  annotation_font_color=ACCENT)
    layout(fig, f"Segments differ by only {spread * 100:.1f} points, so none drives denials",
           "Denial rate (%, 95% CI)", "", xaxis=dict(tickformat=".0%", range=[0, max(0.5, r["hi"].max() * 1.1)]))
    show(fig, "A small spread with overlapping intervals means escalating by this dimension would be misdirected."
         if spread <= 0.05 and len(f) >= 2000 else "Wider spread or small sample here; check segment sizes before acting.")

q = f.assign(q=f["claim_month"].dt.to_period("Q").dt.start_time)
r = rate(q, "q")
fig = go.Figure(go.Scatter(x=r["q"], y=r["rate"], mode="lines+markers+text", line_color=GREY, marker_color=GREY,
                           text=r["rate"].map("{:.1%}".format), textposition="top center", customdata=r["n"],
                           hovertemplate="%{x|%b %Y}<br>Denial rate: %{y:.1%}<br>Claims: %{customdata:,}<extra></extra>"))
layout(fig, f"Denial rate stays {r['rate'].min():.1%}-{r['rate'].max():.1%} in every quarter",
       "Quarter", "Denial rate (%)", yaxis=dict(tickformat=".0%", range=[0, max(0.6, r["rate"].max() + 0.05)]))
note(fig, r.loc[r["rate"].idxmax(), "q"], r["rate"].max(), "Highest quarter", ax=0, ay=-80)
show(fig, "A narrow band means no single quarter explains the problem. Quarters cut by the month filter are partial.")
