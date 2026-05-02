
# prompts/cot.py
# Strategy: CoT — Chain-of-Thought reasoning before picking (paper's Fig. 6)
#
# Matches paper's Fig. 6:
#   - "You are currently playing round N." (no "of T")
#   - "Option J, Option F, or Option B"
#   - Thoughts: then Option: format


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
        f"Which Option do you choose, Option J, Option F, or Option B?\n"
        f"Choose the best action by thinking step by step. "
        f"Your answer MUST be formatted as:\n"
        f"Thoughts: <paragraph explaining your reasoning>\n"
        f"Option: <J, F, or B>"
    )

    return system, user


def parse_response(text: str) -> dict:
    for pattern in (r'\bOption:\s*([JFB])\b', r'\bOption\s+([JFB])\b'):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {"move": m.group(1).upper(), "prediction": None}
    return {"move": _extract_move(text), "prediction": None}


def _extract_move(text: str) -> str | None:
    for pattern in (r'\bOption:\s*([JFB])\b', r'\bOption\s+([JFB])\b'):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    for move in MOVES:
        if re.search(rf'\b{move}\b', text):
            return move
    return None
