# game.py
# Pure game logic for the RPS replication.
# No API calls here — just the rules of the game and metric calculations.
#
# ACTION LABELS — WHY J/F/B NOT ROCK/PAPER/SCISSORS
# The paper uses neutral tokens (J, F, B) specifically to avoid pretraining
# contamination. LLMs have seen vast amounts of RPS strategy text, so using
# "Rock/Paper/Scissors" gives the model prior knowledge about the game
# structure that has nothing to do with ToM. Using neutral labels forces the
# model to learn the payoff structure purely from the history and prompt.
#
# Mapping (internal, for clarity):
#   J = "Rock" equivalent  (beats B, loses to F)
#   F = "Paper" equivalent (beats J, loses to B)
#   B = "Scissors" equivalent (beats F, loses to J)
#
# OPPONENT TYPES

# FixedOpponent:  plays the same move every round
# CycleOpponent:  cycles J → F → B → J → F → B → ...
#                 starting from whichever move is specified


import random

# Neutral action labels — matches paper's Appendix C token choices
MOVES = ["J", "F", "B"]

# Human-readable names for logging/display only (never sent to model)
MOVE_NAMES = {
    "J": "J (Rock-equiv)",
    "F": "F (Paper-equiv)",
    "B": "B (Scissors-equiv)",
}

# What move BEATS each move?
# J beats B, F beats J, B beats F  
BEATS = {
    "J": "F",   # J loses to F  →  F beats J
    "F": "B",   # F loses to B  →  B beats F
    "B": "J",   # B loses to J  →  J beats B
}

# Full payoff table as text — included in every prompt so model knows the rules
# Matches paper's format exactly (Fig. 1 system prompt style)
PAYOFF_TABLE = """The rules of the game are as follows:
If you choose J and the other player chooses J, you receive a score of 0 and the other player receives 0.
If you choose J and the other player chooses F, you receive a score of -1 and the other player receives +1.
If you choose J and the other player chooses B, you receive a score of +1 and the other player receives -1.
If you choose F and the other player chooses J, you receive a score of +1 and the other player receives -1.
If you choose F and the other player chooses F, you receive a score of 0 and the other player receives 0.
If you choose F and the other player chooses B, you receive a score of -1 and the other player receives +1.
If you choose B and the other player chooses J, you receive a score of -1 and the other player receives +1.
If you choose B and the other player chooses F, you receive a score of +1 and the other player receives -1.
If you choose B and the other player chooses B, you receive a score of 0 and the other player receives 0."""



# Opponent classes


class FixedOpponent:
    """Plays the same move every round."""
    def __init__(self, move: str):
        if move not in MOVES:
            raise ValueError(f"Invalid move '{move}'. Must be one of {MOVES}.")
        self.start_move = move
        self.label      = f"fixed-{move}"
        self._move      = move

    def next_move(self) -> str:
        return self._move

    def peek_sequence(self, n: int) -> list:
        return [self._move] * n


class CycleOpponent:
    """
    Cycles through J → F → B → J → F → B → ...
    starting from whichever move you specify.

    start=J  →  J F B J F B ...
    start=F  →  F B J F B J ...
    start=B  →  B J F B J F ...
    """
    def __init__(self, start_move: str):
        if start_move not in MOVES:
            raise ValueError(f"Invalid start_move '{start_move}'. Must be one of {MOVES}.")
        self.start_move = start_move
        self.label      = f"cycle-{start_move}"
        start_idx       = MOVES.index(start_move)
        self._cycle     = MOVES[start_idx:] + MOVES[:start_idx]
        self._step      = 0

    def next_move(self) -> str:
        move = self._cycle[self._step % 3]
        self._step += 1
        return move

    def peek_sequence(self, n: int) -> list:
        return [self._cycle[(self._step + i) % 3] for i in range(n)]


class TitForTatOpponent:
    """
    Tit-for-tat opponent for RPS — matches the paper's Appendix C.3.

    Rule: play the best response to the agent's LAST move.
    i.e. whatever the agent played last round, the opponent plays
    the move that beats it next round.

    Round 1: plays the start_move (no history yet).
    Round 2+: plays BEATS[agent's last move].

    Example (start=J):
      Round 1: opponent plays J  (start move)
      Agent played F in round 1
      Round 2: opponent plays B  (B beats F)
      Agent played J in round 2
      Round 3: opponent plays F  (F beats J)
      ...

    This is harder than fixed or cycle because the sequence depends on
    the agent's own behaviour — a model that plays randomly will face
    a random-looking opponent. A model that locks in one move will face
    the same counter every round.

    runner.py must call update(agent_move) after each round so the
    opponent knows what to play next.
    """

    def __init__(self, start_move: str):
        if start_move not in MOVES:
            raise ValueError(f"Invalid start_move '{start_move}'. Must be one of {MOVES}.")
        self.start_move   = start_move
        self.label        = f"tft-{start_move}"
        self._next_move   = start_move   # what the opponent will play THIS round
        self._last_agent  = None         # agent's last move (set by update())

    def next_move(self) -> str:
        """Return what the opponent plays this round (already computed)."""
        return self._next_move

    def update(self, agent_move: str):
        """
        Called by runner.py after each round with the agent's move.
        Sets the opponent's move for the NEXT round = BEATS[agent_move].
        """
        if agent_move in MOVES:
            self._next_move  = BEATS[agent_move]
            self._last_agent = agent_move

    def peek_sequence(self, n: int) -> list:
        """Can't peek ahead for tit-for-tat — depends on agent behaviour."""
        return [self._next_move] + ['?'] * (n - 1)


def make_opponent(opponent_type: str, start_move: str):
    if opponent_type == "fixed":
        return FixedOpponent(start_move)
    if opponent_type == "cycle":
        return CycleOpponent(start_move)
    if opponent_type == "tft":
        return TitForTatOpponent(start_move)
    raise ValueError(f"Unknown opponent_type '{opponent_type}'. Use 'fixed', 'cycle', or 'tft'.")


def get_opponents_to_run(setting: str) -> list:
    if setting == "all":
        return list(MOVES)
    if setting == "random":
        return [random.choice(MOVES)]
    if setting in MOVES:
        return [setting]
    raise ValueError(f"Unknown opponent setting: '{setting}'.")


def get_all_opponent_configs() -> list:
    configs = []
    for opp_type in ["fixed", "cycle"]:
        for move in MOVES:
            configs.append((opp_type, move))
    return configs


# Game logic


def get_outcome(model_move: str, opponent_move: str) -> str:
    """Return 'win', 'tie', or 'lose' from the model's perspective."""
    if model_move == opponent_move:
        return "tie"
    if BEATS[opponent_move] == model_move:
        return "win"
    return "lose"


def get_score(outcome: str) -> int:
    """Paper's RPS payoff: +1 win, 0 tie, -1 lose."""
    return {"win": 1, "tie": 0, "lose": -1}[outcome]


def regret_per_step(scores: list) -> float:
    """
    ΔFunctional/T from the paper.
    = (optimal_cumulative - actual_cumulative) / T
    Optimal against a fixed or cycle opponent is always +1 per round
    (you can always win if you know the pattern).
    Lower is better. 0.0 = perfect. 2.0 = worst possible.
    """
    rounds      = len(scores)
    actual_sum  = sum(scores)
    optimal_sum = rounds * 1   # always +1 per round if playing optimally
    return (optimal_sum - actual_sum) / rounds


def delta_tom_per_step(scores_if_followed_prediction: list, total_rounds: int) -> float:
    """
    ΔToM/T from the paper.
    = regret of the policy that always plays best-response to its own predictions.
    This is the KEY metric for separating literal from functional ToM.

    If ΔToM/T is low but ΔFunctional/T is high:
      → model predicts correctly but doesn't act on it  (the gap)

    Args:
        scores_if_followed_prediction: per-round score the model WOULD have gotten
                                       if it had always played best-response to
                                       its own prediction
        total_rounds: T
    """
    return regret_per_step(scores_if_followed_prediction)


def pick_random_move() -> str:
    """Fallback when model response can't be parsed."""
    return random.choice(MOVES)


def format_history(history: list) -> str:
    """
    Format game history as plain text for inclusion in prompts.
    Uses neutral J/F/B labels — never Rock/Paper/Scissors.

    Returns lines like:
        In round 1, you chose Option J and the other player chose Option J.
        Thus, you received a score of 0 and the other player received 0.
    Matches paper's prompt format from Figures 1-18.
    """
    if not history:
        return "(no rounds played yet)"

    lines = []
    for i, r in enumerate(history):
        score     = get_score(r["outcome"])
        opp_score = -score if score != 0 else 0
        score_str     = f"+{score}" if score > 0 else str(score)
        opp_score_str = f"+{opp_score}" if opp_score > 0 else str(opp_score)
        lines.append(
            f"In round {i+1}, you chose Option {r['model']} and the other player "
            f"chose Option {r['opponent']}. "
            f"Thus, you received a score of {score_str} and the other player "
            f"received {opp_score_str}."
        )
    return "\n".join(lines)
