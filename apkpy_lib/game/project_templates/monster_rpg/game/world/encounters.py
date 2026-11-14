"""Which wild monster comes out: pure rules, also run by pytest."""
import random

from game.data.defs import EncounterRow, EncounterTable


def pick_row(table: EncounterTable) -> EncounterRow:
    total = 0
    for row in table.rows:
        total += row.weight
    pick = random.randint(1, total)
    for row in table.rows:
        pick -= row.weight
        if pick <= 0:
            return row
    return table.rows[0]


def roll_level(row: EncounterRow) -> int:
    return random.randint(row.min, row.max)
