# prompts/oracle.py
# Strategy: Oracle (Fig. 14 from paper — plain version, no emphasis)
#
# The model is told the opponent's actual move this round, then asked to
# choose. No "IMPORTANT" or "guaranteed" language — matches paper's Fig. 14
# exactly, NOT the Oracle+Max variant (Fig. 15).
#
# Paper's exact structure (Fig. 14):
#   [history]
#   You are currently playing round {N}.
#   The other player will choose Option {X}. Which Option do you choose,
#   Option J, Option F, or Option B?
#   Your answer MUST be formatted like:
#   Option: <J or F or B>
#
# Gap = 100% - Win%
# Any loss is a functional failure — the answer was given.


import re
from game import MOVES, PAYOFF_TABLE, format_history


def build_prompt(history, round_num, total_rounds, opponent_move):
    system = (
        f"You are playing a game repeatedly with another player. "
        f"In this game, you can choose between Option J, Option F, and Option B. "
        f"You will play {total_rounds} rounds in total with the same player.\n\n"
        f"{PAYOFF_TABLE}"
    )

    user = (
        f"{format_history(history)}\n\n"
        f"You are currently playing round {round_num}.\n"
        f"The other player will choose Option {opponent_move}. "
        f"Which Option do you choose, Option J, Option F, or Option B?\n"
        f"Your answer MUST be formatted like:\n"
        f"Option: <J or F or B>"
    )

    return system, user


def parse_response(text: str) -> dict:
    move = _extract_move(text)
    return {"move": move, "prediction": None}


def _extract_move(text: str) -> str | None:
    match = re.search(r'\bOption:\s*([JFB])\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match = re.search(r'\bOption\s+([JFB])\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    for move in MOVES:
        if re.search(rf'\b{move}\b', text):
            return move
    return None
