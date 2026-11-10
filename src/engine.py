"""
Arenna Points engine. It does not know which club the data comes from:
it takes the standard activities table that each club adapter builds.

  compute_points(activities)   -> point_events: every point earned or lost, with its reason
  player_categories(...)       -> the category each player competes in
  monthly_ranking(...)         -> each category's ranking and the winner's prize
"""

import pandas as pd

from . import rules as R


def category_for_level(level: float) -> str:
    for name, low, high in R.CATEGORIES:
        if low <= level < high:
            return name
    return "build"


def is_off_peak(moment: pd.Timestamp) -> bool:
    h = R.OFF_PEAK_HOURS
    return moment.weekday() in h["days"] and h["start"] <= moment.hour < h["end"]


def compute_points(acts: pd.DataFrame, use_off_peak: bool = True) -> pd.DataFrame:
    events = []
    played = acts[acts["status"] == "played"]

    for a in played.itertuples():
        label = R.ACTIVITY_LABEL[a.activity]
        events.append((a.player, a.played_at, a.activity, label, R.ACTIVITY_POINTS[a.activity]))
        if use_off_peak and a.has_time and is_off_peak(a.played_at):
            events.append((a.player, a.played_at, "off_peak", f"{label}, off-peak hours", R.OFF_PEAK_BONUS))

    for a in acts[acts["status"] == "no_show"].itertuples():
        events.append((a.player, a.played_at, "no_show",
                       f"No-show: {R.ACTIVITY_LABEL[a.activity]}", R.NO_SHOW_PENALTY))

    events += _streaks(played)

    pe = pd.DataFrame(events, columns=["player", "played_at", "activity", "reason", "points"])
    pe["month"] = pe["played_at"].dt.strftime("%Y-%m")
    return pe.sort_values(["player", "played_at"]).reset_index(drop=True)


def _streaks(played: pd.DataFrame) -> list:
    """+20 every time a player completes 4 consecutive weeks with activity.
    Credited on the first activity of the week that completes the streak."""
    monday = (played["played_at"] - pd.to_timedelta(played["played_at"].dt.weekday, unit="D")).dt.normalize()
    first_of_week = played.assign(week=monday).groupby(["player", "week"])["played_at"].min()

    events = []
    for player, weeks in first_of_week.groupby(level="player"):
        run, previous = 0, None
        for (_, week), moment in weeks.items():
            run = run + 1 if previous is not None and week - previous == pd.Timedelta(days=7) else 1
            if run % R.STREAK_WEEKS == 0:
                events.append((player, moment, "streak", f"{run}-week streak", R.STREAK_BONUS))
            previous = week
    return events


def player_categories(acts: pd.DataFrame) -> pd.DataFrame:
    """Each player competes in the category they played most (by program level).
    Players who only took private lessons have no recorded level and no category."""
    with_level = acts.dropna(subset=["level"])
    cat = with_level.assign(category=with_level["level"].map(category_for_level))
    main = cat.groupby("player")["category"].agg(lambda s: s.value_counts().idxmax())
    everyone = pd.Series(acts["player"].unique(), name="player")
    return everyone.to_frame().merge(main.reset_index(), how="left").fillna({"category": "none"})


def choose_prize(spend: float):
    for limit, membership, cost in R.PRIZES:
        if spend < limit:
            return f"One month of {membership}", cost


def monthly_ranking(pe: pd.DataFrame, spend: pd.DataFrame, players: pd.DataFrame, month: str) -> pd.DataFrame:
    points = (pe[pe["month"] == month].groupby("player")
              .agg(points=("points", "sum"),
                   activities=("activity", lambda s: s.isin(list(R.ACTIVITY_POINTS)).sum()))
              .reset_index())
    table = (points.merge(players, on="player")
             .merge(spend[spend["month"] == month][["player", "spend"]], on="player", how="left")
             .fillna({"spend": 0}))
    table = table[table["category"] != "none"]

    # Tie-break (provisional): with equal points, the higher spender wins
    table = table.sort_values(["category", "points", "spend"], ascending=[True, False, False])
    table["rank"] = table.groupby("category").cumcount() + 1

    table["prize"], table["prize_cost"] = "", 0.0
    for i in table.index[table["rank"] == 1]:
        table.loc[i, ["prize", "prize_cost"]] = choose_prize(table.at[i, "spend"])

    table.insert(0, "month", month)
    return table[["month", "category", "rank", "player", "points", "activities",
                  "spend", "prize", "prize_cost"]].reset_index(drop=True)
