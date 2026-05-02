
# Runs one complete experiment: one model, one strategy, one opponent, N rounds.
#
# SocialQA two-call structure:
#   Call 1: retrospective prediction (what did opponent play last round?)
#   Call 2: social prompt with prediction injected (Fig. 18)
#   fallback_used flag logged when Call 1 fails to parse
#
# TitForTat: opponent.update(agent_move) called after each round.


import time

import config
from game import MOVES, BEATS, get_outcome, get_score, regret_per_step, pick_random_move
from api_client import call_model
from prompts.social_qa import build_predict_prompt, parse_prediction, build_social_prompt


def run_strategy(model_id, strat_key, strat_config, opponent, total_rounds):

    build_prompt   = strat_config["build"]
    parse_response = strat_config["parse"]
    label          = strat_config["label"]

    history        = []
    scores         = []
    round_records  = []
    opponent_moves = []

    pred_correct   = 0
    pred_total     = 0
    parse_failures = 0
    tom_cf_scores  = []   # counterfactual scores for ΔToM/T

    is_tft = hasattr(opponent, 'update')

    print(f"\n  Strategy: {label}")
    print(f"  Opponent: {opponent.label}")
    print(f"  {'Round':<7} {'Model':<7} {'Opp':<7} {'Outcome':<8} {'Score':<7} {'WinRate'}")
    print(f"  {'-'*55}")

    for round_num in range(1, total_rounds + 1):

        opp_move = opponent.next_move()
        opponent_moves.append(opp_move)

        # SocialQA: two calls 
        clean_prediction = None
        fallback_used    = False

        if strat_key == "SocialQA":
            # Call 1: retrospective prediction
            pred_sys, pred_usr = build_predict_prompt(history, round_num, total_rounds)
            pred_text = call_model(model_id, pred_sys, pred_usr)
            if pred_text:
                clean_prediction = parse_prediction(pred_text)
            if clean_prediction is None:
                fallback_used = True   # Call 1 failed — Call 2 will use QA fallback

            time.sleep(config.SLEEP_BETWEEN_ROUNDS)

            # Call 2: social prompt with prediction injected
            soc_sys, soc_usr = build_social_prompt(
                history, round_num, total_rounds, clean_prediction
            )
            raw_text = call_model(model_id, soc_sys, soc_usr)

        else:
            # All other strategies: single call
            sys_p, usr_p = build_prompt(history, round_num, total_rounds, opp_move)
            raw_text = call_model(model_id, sys_p, usr_p)

        #  Parse response 
        if raw_text:
            parsed = parse_response(raw_text)
        else:
            parsed = {"move": None, "prediction": None}

        if parsed["move"] not in MOVES:
            parsed["move"] = pick_random_move()
            parse_failures += 1

        model_move = parsed["move"]
        prediction = clean_prediction if strat_key == "SocialQA" else parsed["prediction"]

        # Prediction tracking 
        if prediction is not None:
            pred_total += 1
            if prediction == opp_move:
                pred_correct += 1
            # Counterfactual: score if played best-response to own prediction
            cf_outcome = get_outcome(BEATS[prediction], opp_move)
            tom_cf_scores.append(get_score(cf_outcome))
        else:
            tom_cf_scores.append(0)

        # Outcome 
        outcome = get_outcome(model_move, opp_move)
        score   = get_score(outcome)
        scores.append(score)

        history.append({"model": model_move, "opponent": opp_move, "outcome": outcome})

        if is_tft:
            opponent.update(model_move)

        #  Display 
        wins_so_far = sum(1 for s in scores if s == 1)
        score_str   = f"+{score}" if score > 0 else str(score)
        print(
            f"  {round_num:<7} {model_move:<7} {opp_move:<7} "
            f"{outcome:<8} {score_str:<7} {wins_so_far/round_num*100:.1f}%",
            end="\r"
        )

        round_records.append({
            "round":            round_num,
            "model_move":       model_move,
            "opponent":         opp_move,
            "outcome":          outcome,
            "score":            score,
            "prediction":       prediction,
            "clean_prediction": clean_prediction,
            "fallback_used":    fallback_used,
            "raw_text":         raw_text,
        })

        time.sleep(config.SLEEP_BETWEEN_ROUNDS)

    print()

    #  Metrics 
    wins  = sum(1 for s in scores if s == 1)
    ties  = sum(1 for s in scores if s == 0)
    loses = sum(1 for s in scores if s == -1)

    win_rate         = wins / total_rounds * 100
    delta_functional = regret_per_step(scores)
    tom_pct          = (pred_correct / pred_total * 100) if pred_total > 0 else None
    delta_tom        = regret_per_step(tom_cf_scores) if pred_total > 0 else None

    if strat_key == "Oracle":
        gap = 100.0 - win_rate
    elif delta_tom is not None:
        gap = delta_functional - delta_tom
    else:
        gap = None

    print(f"  {'─'*55}")
    print(f"  Win: {wins} | Tie: {ties} | Lose: {loses}")
    print(f"  Win rate:       {win_rate:.1f}%")
    print(f"  ΔFunctional/T:  {delta_functional:.3f}")
    if delta_tom  is not None: print(f"  ΔToM/T:         {delta_tom:.3f}")
    if tom_pct    is not None: print(f"  ToM%:           {tom_pct:.1f}%")
    if gap        is not None: print(f"  Gap:            {gap:+.3f}  ← ToM gap")
    if parse_failures > 0:     print(f"  Parse fails:    {parse_failures}")

    return {
        "model_id":          model_id,
        "strategy":          strat_key,
        "strategy_label":    label,
        "opponent_type":     opponent.label,
        "opponent_start":    opponent.start_move,
        "opponent_sequence": opponent_moves,
        "total_rounds":      total_rounds,
        "wins":              wins,
        "ties":              ties,
        "loses":             loses,
        "win_rate":          round(win_rate, 2),
        "delta_functional":  round(delta_functional, 4),
        "delta_tom":         round(delta_tom, 4) if delta_tom is not None else None,
        "tom_pct":           round(tom_pct, 2)   if tom_pct  is not None else None,
        "gap":               round(gap, 4)        if gap      is not None else None,
        "parse_failures":    parse_failures,
        "round_records":     round_records,
    }
