"""
Arenna Points rules.

Every rule the club might want to change lives in this file.
Changing a rule means changing a number here and nowhere else.
"""

# Points per activity (only activities that were actually played count)
ACTIVITY_POINTS = {
    "open_play": 10,
    "clinic": 10,
    "private_lesson": 20,
}

ACTIVITY_LABEL = {  # what the player sees in their history
    "open_play": "Open play",
    "clinic": "Clinic",
    "private_lesson": "Private lesson",
}

OFF_PEAK_BONUS = 5
STREAK_BONUS = 20
STREAK_WEEKS = 4  # every 4 consecutive weeks with at least one activity
NO_SHOW_PENALTY = -5

# Off-peak hours (provisional, to be confirmed by the club).
# Days: 0 = Monday ... 6 = Sunday. The activity starts within [start, end).
OFF_PEAK_HOURS = {"days": [0, 1, 2, 3, 4], "start": 9, "end": 16}

# Categories by playing level: (name, minimum level included, maximum level excluded)
CATEGORIES = [
    ("build", 0.0, 2.0),
    ("progress", 2.0, 3.0),
    ("perform", 3.0, 99.0),
]

# Prize depends on what the winner spent that month, at Arenna's prices:
# (spend upper bound excluded, membership, cost to the club)
PRIZES = [
    (200, "Social", 90.00),
    (350, "Active", 127.50),
    (float("inf"), "Elite", 187.50),
]
