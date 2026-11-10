"""
Adapter for a padel club's Playbypoint payments report.

Turns the raw CSV into the two standard tables the engine understands:
  - activities: one row per open play, clinic or private lesson that was played
  - spend: what each player spent at the club each month

Each club gets its own adapter. The points engine never changes:
supporting another club means writing another file like this one.

Cleaning decisions (from notebooks/01_exploration.ipynb):
  1. Only Open play, Clinic and Lesson count.
  2. Payments with status 'Totally refunded' or 'Refunded to credit' are dropped:
     they are exactly the payments that a 'Reversal of ...' row cancels.
     The reversal rows themselves are not used.
  3. Rows with NO status DO count: they are payments made with club credits.
  4. 'Guest Player' (not a real person) and Junior programs are dropped.
  5. Players are identified by normalized name (the report has no phone or
     email) and anonymized as 'Player 001'.
  6. The play date is parsed from the 'description' text ("... - May 8 2025");
     when missing, the payment date is used (median gap payment-to-play: 1 day).
     Private lessons carry date and time in 'date_and_time'.
"""

import re

import pandas as pd

ACTIVITY_CATEGORIES = {"Open play": "open_play", "Clinic": "clinic", "Lesson": "private_lesson"}
CANCELLED_STATUSES = ["Totally refunded", "Refunded to credit"]
SPEND_CATEGORIES = ["Reservation", "Open play", "Clinic", "Lesson", "Event",
                    "Tournament", "Ball machine", "Merchandise", "League"]

DATE_IN_DESCRIPTION = r"-\s*([A-Z][a-z]{2} \d{1,2} \d{4})\s*$"
LEVEL_IN_DESCRIPTION = r"level\s*(\d+(?:\.\d+)?)"


def load(path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["player_key"] = (df["name"].fillna("").str.strip()
                        .str.replace(r"\s+", " ", regex=True).str.lower())
    df["payment_day"] = pd.to_datetime(df["payment_date"].str[:10])
    return df


def anonymization_map(df: pd.DataFrame) -> pd.DataFrame:
    """Real name -> 'Player 001', in order of first appearance. Stays in data/ only."""
    keys = df.loc[df["player_key"] != "", "player_key"].drop_duplicates()
    keys = keys[keys != "guest player"]
    return pd.DataFrame({
        "player_key": keys.values,
        "player": [f"Player {i:03d}" for i in range(1, len(keys) + 1)],
    })


def _valid(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["status"].isin(CANCELLED_STATUSES) & (df["player_key"] != "guest player")
              & (df["player_key"] != "")]


def _level(description: pd.Series) -> pd.Series:
    level = description.str.extract(LEVEL_IN_DESCRIPTION, flags=re.IGNORECASE)[0].astype(float)
    is_intro = description.str.contains("intro to padel", case=False)
    return level.mask(is_intro & level.isna(), 1.0)


def activities(df: pd.DataFrame, names: pd.DataFrame):
    """Returns (activities, cleaning log)."""
    log = {}
    base = df[df["category"].isin(ACTIVITY_CATEGORIES)]
    log["open play, clinic and lesson rows"] = len(base)

    valid = _valid(base)
    log["dropped: refunded or Guest Player"] = len(base) - len(valid)

    desc = valid["description"].fillna("")
    is_junior = desc.str.contains("junior|ages", case=False)
    log["dropped: Junior programs"] = int(is_junior.sum())
    valid, desc = valid[~is_junior], desc[~is_junior]

    acts = pd.DataFrame({
        "player_key": valid["player_key"],
        "activity": valid["category"].map(ACTIVITY_CATEGORIES),
        "level": _level(desc),
        "amount": valid["amount"],
    })

    # Play date
    text_date = pd.to_datetime(desc.str.extract(DATE_IN_DESCRIPTION)[0], format="%b %d %Y")
    lesson_time = pd.to_datetime(
        valid["date_and_time"].str.replace(r"^(\w+ \d+, \d{4}) / (\d+:\d+ [AP]M).*$", r"\1 \2", regex=True),
        format="%b %d, %Y %I:%M %p", errors="coerce")
    no_date = text_date.isna() & lesson_time.isna()
    log["play date taken from payment date"] = int(no_date.sum())

    acts["played_at"] = lesson_time.fillna(text_date).fillna(valid["payment_day"])
    acts["has_time"] = lesson_time.notna()
    acts["status"] = "played"  # a payments report has no no-shows

    acts = acts.merge(names, on="player_key").drop(columns="player_key")
    log["activities that earn points"] = len(acts)
    return acts.sort_values("played_at").reset_index(drop=True), log


def monthly_spend(df: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """Spend per player per payment month. Excludes memberships and credit top-ups."""
    spend = _valid(df[df["category"].isin(SPEND_CATEGORIES)])
    spend = spend.assign(month=spend["payment_day"].dt.strftime("%Y-%m"))
    out = spend.groupby(["player_key", "month"], as_index=False)["amount"].sum()
    return out.rename(columns={"amount": "spend"}).merge(names, on="player_key").drop(columns="player_key")
