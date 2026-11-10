"""
Simulates Arenna Points over 12 months of real payments from a padel club.

Usage:
  python simulate.py

Reads  data/club_payments.csv  (private, never committed)
Writes data/player_map.csv     (real name -> Player 001; private)
       results/*.csv           (anonymized)
       figures/*.png
"""

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src import club_source, engine, rules  # noqa: E402

DATA = Path("data")
RESULTS = Path("results")
FIGURES = Path("figures")

# May 2025 starts on the 8th (the club's opening). May 2026 is dropped: only 8 days.
MONTHS = [str(p) for p in pd.period_range("2025-05", "2026-04", freq="M")]

# Palette (validated for three categories) and ink
COLOR = {"build": "#2a78d6", "progress": "#eb6834", "perform": "#1baf7a"}
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
MONTH_NAME = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_label(month: str) -> str:
    year, m = month.split("-")
    return f"{MONTH_NAME[int(m) - 1]}\n{year[2:]}"


def winners_no_repeat(ranking: pd.DataFrame) -> pd.DataFrame:
    """Alternative rule: last month's winner cannot win this month.
    The prize goes to the best-ranked player who did not win last month."""
    rows, previous = [], set()
    for month in MONTHS:
        this_month = ranking[ranking["month"] == month]
        current = set()
        for category, table in this_month.groupby("category"):
            eligible = table[~table["player"].isin(previous)].iloc[0]
            prize, cost = engine.choose_prize(eligible["spend"])
            rows.append({**eligible.to_dict(), "prize": prize, "prize_cost": cost})
            current.add(eligible["player"])
        previous = current
    return pd.DataFrame(rows)


def style(ax, title: str, subtitle: str):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=10, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.figure.text(0.04, 0.95, title, fontsize=14, fontweight="bold", color=INK, va="top")
    ax.figure.text(0.04, 0.89, subtitle, fontsize=10.5, color=INK_2, va="top")


def figure_cost(winners: pd.DataFrame):
    cost = winners.groupby("month")["prize_cost"].sum().reindex(MONTHS)
    cap = 3 * rules.PRIZES[-1][2]
    months_at_cap = int((cost == cap).sum())

    fig, ax = plt.subplots(figsize=(9, 4.6))
    fig.subplots_adjust(top=0.78, left=0.08, right=0.97, bottom=0.14)
    ax.bar(range(len(MONTHS)), cost.values, width=0.62, color=COLOR["build"])
    ax.axhline(cap, color=INK_2, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(len(MONTHS) - 0.5, cap + 12, f"Cap: three Elite prizes, ${cap:,.2f}",
            ha="right", fontsize=9.5, color=INK_2)
    ax.set_xticks(range(len(MONTHS)), [month_label(m) for m in MONTHS])
    ax.set_ylim(0, cap * 1.18)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    style(ax, f"Prizes would cost ${cost.sum():,.0f} a year",
          f"Monthly cost of the three prizes (one per category). The cap is reached in {months_at_cap} of 12 months.")
    fig.savefig(FIGURES / "1_monthly_cost.png", dpi=200)
    plt.close(fig)


def figure_spend(winners: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 4.8))
    fig.subplots_adjust(top=0.78, left=0.09, right=0.84, bottom=0.14)
    x = {m: i for i, m in enumerate(MONTHS)}
    offset = {"build": -0.18, "progress": 0.0, "perform": 0.18}
    for category in ["build", "progress", "perform"]:
        table = winners[winners["category"] == category]
        ax.scatter([x[m] + offset[category] for m in table["month"]], table["spend"],
                   s=58, color=COLOR[category], edgecolor=SURFACE, linewidth=1.5,
                   label=category.title(), zorder=3)
    for limit, step in [(200, "Social → Active"), (350, "Active → Elite")]:
        ax.axhline(limit, color=INK_2, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(len(MONTHS) - 0.45, limit, f"${limit}\n{step}", va="center", fontsize=9, color=INK_2)
    elite = int((winners["spend"] >= 350).sum())
    ax.set_xticks(range(len(MONTHS)), [month_label(m) for m in MONTHS])
    ax.set_xlim(-0.6, len(MONTHS) - 0.5)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=INK_2, ncol=3)
    ax.set_ylim(0, winners["spend"].max() * 1.15)
    style(ax, f"{elite} of {len(winners)} winners spent more than $350",
          "Each winner's spend in their winning month. Above $350 the prize is a month of Elite.")
    fig.savefig(FIGURES / "2_winner_spend.png", dpi=200)
    plt.close(fig)


def figure_repeat_winners(winners: pd.DataFrame):
    wins = (winners.groupby(["player", "category"]).size().rename("wins")
            .reset_index().sort_values("wins"))
    repeat = wins[wins["wins"] >= 2]
    repeat_prizes = int(repeat["wins"].sum())

    fig, ax = plt.subplots(figsize=(9, 0.5 * len(repeat) + 2.2))
    fig.subplots_adjust(top=0.80, left=0.17, right=0.95, bottom=0.08)
    ax.barh(range(len(repeat)), repeat["wins"], height=0.58,
            color=[COLOR[c] for c in repeat["category"]])
    for i, row in enumerate(repeat.itertuples()):
        ax.text(row.wins + 0.08, i, f"{row.wins} prizes · {row.category.title()}",
                va="center", fontsize=9.5, color=INK_2)
    ax.set_yticks(range(len(repeat)), repeat["player"])
    ax.set_xticks([])
    ax.set_xlim(0, repeat["wins"].max() + 1.6)
    style(ax, f"{len(repeat)} players take {repeat_prizes} of the {len(winners)} prizes",
          f"Players who won their category in two or more months. {wins['player'].nunique()} different winners in total.")
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    fig.savefig(FIGURES / "3_repeat_winners.png", dpi=200)
    plt.close(fig)


def main():
    RESULTS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)

    raw = club_source.load(DATA / "club_payments.csv")
    names = club_source.anonymization_map(raw)
    names.to_csv(DATA / "player_map.csv", index=False)

    activities, log = club_source.activities(raw, names)
    spend = club_source.monthly_spend(raw, names)
    players = engine.player_categories(activities)

    # The payments report has no start time for open plays and clinics, so the
    # off-peak bonus is switched off to treat every player the same way.
    points = engine.compute_points(activities, use_off_peak=False)
    ranking = pd.concat([engine.monthly_ranking(points, spend, players, m) for m in MONTHS])
    winners = ranking[ranking["rank"] == 1]
    alternative = winners_no_repeat(ranking)

    points.drop(columns="played_at").assign(date=points["played_at"].dt.date).to_csv(
        RESULTS / "point_events.csv", index=False)
    ranking[ranking["rank"] <= 10].to_csv(RESULTS / "top10_ranking.csv", index=False)
    winners.to_csv(RESULTS / "winners.csv", index=False)

    figure_cost(winners)
    figure_spend(winners)
    figure_repeat_winners(winners)

    print("Cleaning")
    for key, value in log.items():
        print(f"  {value:>6,}  {key}")
    print(f"\nPlayers per category\n{players['category'].value_counts().to_string()}")
    print(f"\nPrizes in 12 months: {len(winners)}  ·  different winners: {winners['player'].nunique()}")
    print(f"Total cost: ${winners['prize_cost'].sum():,.2f}  ·  "
          f"winners' spend in their winning month: ${winners['spend'].sum():,.2f}")
    print(f"With the 'no back-to-back wins' rule: {alternative['player'].nunique()} different winners, "
          f"cost ${alternative['prize_cost'].sum():,.2f}")


if __name__ == "__main__":
    main()
