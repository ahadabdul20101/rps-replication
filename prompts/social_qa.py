# prompts/social_qa.py
# Strategy: Social Prompting (paper's Fig. 18)
#
# TWO API calls per round:
#
# CALL 1 — Prospective Literal ToM:
#   Given the full history, predict what the opponent will play THIS round.
#   Explicitly shows the opponent's move sequence and asks for the next move.
#   This nudges the model to extrapolate the pattern, not just recall the last move.
#
#   on retrospective vs prospective:
#   An earlier version used a retrospective prompt (Fig. 5 style: "what did the
#   opponent play last round?") which caused a systematic 1-round lag — the model
#   recalled the previous opponent move from the history and used it as the
#   "prediction" for the current round. In a cycling opponent this is always wrong.
#   The fix is to ask prospectively with the opponent's sequence made explicit.
#
# CALL 2 — Social Prompting (Fig. 18):
#   "Given that you predict the other player will choose Option {X} in round N,
#    which Option do you choose?"
#   Prediction from Call 1 is inserted literally into the prompt.


import re
from game import MOVES, PAYOFF_TABLE, format_history


def _system(total_rounds: int) -> str:
    return (
        f"You are playing a game repeatedly with another player. "
        f"In this game, you can choose between Option J, Option F, and Option B. "
        f"You will play {total_rounds} rounds in total with the same player.\n\n"
        f"{PAYOFF_TABLE}"
    )


# CALL 1: Prospective prediction 

def build_predict_prompt(history, round_num, total_rounds):
    """
    Prospective: given the history, predict what the opponent will play
    in the CURRENT round before either player has moved.

    We explicitly list the opponent's move sequence to help the model
    see the pattern and extrapolate — rather than just recalling the last move.
    """
    system = _system(total_rounds)

    if len(history) == 0:
        user = (
            f"(no rounds played yet)\n\n"
            f"You are currently playing round {round_num}.\n"
            f"Which Option do you think the other player will choose in this round, "
            f"Option J, Option F, or Option B?\n"
            f"Your answer MUST be formatted like:\n"
            f"Option: <J, F, or B>"
        )
    else:
        # Explicitly list opponent's sequence to surface the pattern
        opp_sequence = ", ".join(
            f"round {i+1}: {r['opponent']}"
            for i, r in enumerate(history)
        )

        user = (
            f"{format_history(history)}\n\n"
            f"The other player has chosen: {opp_sequence}.\n"
            f"Based on this pattern, which Option do you predict the other player "
            f"will choose in round {round_num}?\n"
            f"Your answer MUST be formatted like:\n"
            f"Option: <J, F, or B>"
        )

    return system, user


def parse_prediction(text: str) -> str | None:
    return _extract_move(text)


# CALL 2: Social Prompting (Fig. 18) 

def build_social_prompt(history, round_num, total_rounds, prediction):
    """
    Paper's Fig. 18. Prediction from Call 1 inserted into the prompt text.
    If prediction is None (Call 1 parse failed), falls back to plain QA.
    """
    system = _system(total_rounds)

    if prediction is not None:
        user = (
            f"{format_history(history)}\n"
            f"Given that you predict the other player will choose "
            f"Option {prediction} in round {round_num}, which Option do you "
            f"think is best to choose for you in this round, "
            f"Option J, Option F, or Option B?\n"
            f"Your answer MUST be formatted like:\n"
            f"Option: <J, F, or B>"
        )
    else:
        # Fallback — Call 1 failed, degrade to QA
        user = (
            f"{format_history(history)}\n\n"
            f"You are currently playing round {round_num}.\n"
            f"Which Option do you choose, Option J, Option F, or Option B?\n"
            f"Your answer MUST be formatted like:\n"
            f"Option: <J, F, or B>"
        )

    return system, user


def parse_response(text: str) -> dict:
    return {"move": _extract_move(text), "prediction": None}


def build_prompt(history, round_num, total_rounds, opponent_move):
    """Registry-compatibility shim. runner.py calls build_social_prompt directly."""
    return build_social_prompt(history, round_num, total_rounds, None)


#  Shared helper 

def _extract_move(text: str) -> str | None:
    for pattern in (r'\bOption:\s*([JFB])\b', r'\bOption\s+([JFB])\b'):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    for move in MOVES:
        if re.search(rf'\b{move}\b', text):
            return move
    return None
