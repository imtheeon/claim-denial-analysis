import pandas as pd
import plotly.express as px
import streamlit as st

BLUE, ORANGE, GRAY = "#2a6fb0", "#d9622b", "#9aa5b1"
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
    return g.groupby(by, observed=True)["is_denied"].mean().mul(100).reset_index(name="rate")


def style(fig, x, y, **kw):
    fig.update_layout(xaxis_title=x, yaxis_title=y, margin=dict(t=20, b=10, l=10, r=10),
                      legend_title_text="", height=340, **kw)
    return fig


df = load()
st.title("Claim denial analysis")
st.caption("Synthetic data (Kaggle DenialIQ, 120k claims, 2021-01 to 2024-06). Denial rate = denied / adjudicated.")

with st.sidebar:
    st.header("Filters")
    payer = st.multiselect("Payer", sorted(df["payer_type"].unique()))
    spec = st.multiselect("Specialty", sorted(df["provider_specialty"].unique()))
    dx = st.multiselect("Diagnosis chapter", sorted(df["dx_chapter"].unique()))
    months = sorted(df["claim_month"].dt.to_period("M").unique())
    lo, hi = st.select_slider("Claim month", months, value=(months[0], months[-1]),
                              format_func=lambda p: p.strftime("%b %Y"))

f = df[df["is_adjudicated"] & df["claim_month"].dt.to_period("M").between(lo, hi)]
for col, sel in [("payer_type", payer), ("provider_specialty", spec), ("dx_chapter", dx)]:
    if sel:
        f = f[f[col].isin(sel)]
if f.empty or not f["is_denied"].any():
    st.warning("No denied claims match these filters.")
    st.stop()

den = f[f["is_denied"]]
overall = f["is_denied"].mean() * 100
low_share = den.loc[den["low_doc"], "claim_amount_usd"].sum() / max(den["claim_amount_usd"].sum(), 1) * 100
k = st.columns(5)
k[0].metric("Adjudicated claims", f"{len(f):,}")
k[1].metric("Denial rate", f"{overall:.1f}%")
k[2].metric("Denied $", f"${den['claim_amount_usd'].sum() / 1e6:,.2f}M")
k[3].metric("Recoverable $", f"${den['estimated_recovery_usd'].sum() / 1e6:,.2f}M")
k[4].metric("Denied $ from low-doc claims", f"{low_share:.0f}%", help="Documentation completeness < 0.7")

c1, c2 = st.columns(2)
with c1.container(border=True):
    st.subheader("Denial rate by documentation completeness")
    r = rate(f, "doc_band")
    fig = px.bar(r, x="doc_band", y="rate", text=r["rate"].map("{:.0f}%".format),
                 color_discrete_sequence=[BLUE])
    st.plotly_chart(style(fig, "Documentation completeness", "Denial rate (%)", yaxis_range=[0, 105]),
                    width="stretch")
    st.caption("Denials collapse once documentation reaches 0.7; below it, most claims are denied.")
with c2.container(border=True):
    st.subheader("Prior-auth gap vs documentation")
    r = rate(f.assign(auth=f["auth_gap"].map({True: "Auth gap", False: "No auth gap"}),
                      docs=f["low_doc"].map({True: "Low doc (<0.7)", False: "High doc (>=0.7)"})),
             ["auth", "docs"])
    fig = px.bar(r, x="auth", y="rate", color="docs", barmode="group",
                 text=r["rate"].map("{:.0f}%".format),
                 color_discrete_map={"Low doc (<0.7)": ORANGE, "High doc (>=0.7)": BLUE})
    st.plotly_chart(style(fig, "Prior-auth status", "Denial rate (%)", yaxis_range=[0, 105]),
                    width="stretch")
    st.caption("Across the full dataset, an auth gap adds about 11 points within a documentation band, while documentation moves the rate by 60+ points: fix docs first.")

c3, c4 = st.columns(2)
with c3.container(border=True):
    st.subheader("Denied $ by category")
    g = den.groupby("denial_category").agg(billed=("claim_amount_usd", "sum"),
                                           rec=("estimated_recovery_usd", "sum"))
    g["Not recoverable"] = g["billed"] - g["rec"]
    g = g.rename(columns={"rec": "Recoverable"}).sort_values("billed").drop(columns="billed")
    fig = px.bar(g, orientation="h", barmode="stack",
                 color_discrete_map={"Recoverable": BLUE, "Not recoverable": GRAY})
    fig.update_xaxes(tickprefix="$", tickformat=",.2s")
    st.plotly_chart(style(fig, "Denied billed $", "Denial category"), width="stretch")
    top = g["Recoverable"].idxmax()
    st.caption(f"{top.replace('_', ' ').capitalize()} holds the most recoverable dollars in this selection.")
with c4.container(border=True):
    st.subheader("Denial rate by segment")
    dim = st.selectbox("Segment", ["payer_type", "provider_specialty", "dx_chapter"],
                       format_func=lambda c: {"payer_type": "Payer", "provider_specialty": "Specialty",
                                              "dx_chapter": "Diagnosis chapter"}[c])
    r = rate(f, dim).sort_values("rate")
    fig = px.bar(r, x="rate", y=dim, orientation="h", color_discrete_sequence=[BLUE])
    fig.add_vline(x=overall, line_dash="dash", line_color=ORANGE,
                  annotation_text=f"Overall {overall:.1f}%")
    st.plotly_chart(style(fig, "Denial rate (%)", "", xaxis_range=[0, 100]), width="stretch")
    spread = r["rate"].max() - r["rate"].min()
    st.caption(f"Rates span {r['rate'].min():.0f}-{r['rate'].max():.0f}% across segments. "
               + ("Small spread: this dimension is not where denials come from." if spread <= 5 and len(f) >= 2000
                  else "Wider spread or small sample here; check segment sizes before acting."))

with st.container(border=True):
    st.subheader("Quarterly denial rate")
    q = f.assign(q=f["claim_month"].dt.to_period("Q").dt.start_time)
    r = rate(q, "q")
    fig = px.line(r, x="q", y="rate", markers=True, color_discrete_sequence=[BLUE])
    fig.update_yaxes(ticksuffix="%", range=[0, max(60, r["rate"].max() + 5)])
    st.plotly_chart(style(fig, "Quarter", "Denial rate (%)"), width="stretch")
    st.caption(f"Quarterly rate ranges {r['rate'].min():.0f}-{r['rate'].max():.0f}%; a narrow band means no single quarter explains the problem. "
               "Quarters cut by the month filter are partial.")
