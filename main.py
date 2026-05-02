# db handeling done with claude, html also made with claude but havent really used it so far.
# 
# Usage:
#   python main.py                                          # config.py defaults
#   python main.py --rounds 20                             # quick test
#   python main.py --opponent-type fixed                   # fixed only
#   python main.py --opponent-type cycle                   # cycle only
#   python main.py --opponent-type tft                     # tit-for-tat only
#   python main.py --opponent-type both                    # fixed + cycle
#   python main.py --opponent-type all                     # fixed + cycle + tft
#   python main.py --opponent-move J                       # one start move
#   python main.py --opponent-move all                     # all 3 start moves
#   python main.py --strategies QA Oracle                  # subset
#   python main.py --db-summary                            # show DB contents
#
# SAVING:
#   Results go to SQLite (results/results.db) — append only, never overwritten.
#   Also saves a compact JSON log (results/all_runs.json) for compatibility.
#   Use --db-summary to see all results across runs.


import argparse
import json
import os
import sys
import statistics
from datetime import datetime

import config
from game import MOVES, BEATS, make_opponent, get_opponents_to_run
from runner import run_strategy
from prompts import STRATEGY_REGISTRY
from database import Database


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="ToM Gap RPS Replication")
    parser.add_argument("--rounds", type=int, default=config.ROUNDS)
    parser.add_argument(
        "--opponent-type", dest="opponent_type",
        choices=["fixed", "cycle", "tft", "both", "all"],
        default=config.OPPONENT_TYPE,
        help="'fixed', 'cycle', 'tft', 'both' (fixed+cycle), 'all' (fixed+cycle+tft)"
    )
    parser.add_argument(
        "--opponent-move", dest="opponent_move",
        choices=MOVES + ["random", "all"],
        default=config.OPPONENT_MOVE,
    )
    parser.add_argument(
        "--strategies", nargs="+",
        choices=list(STRATEGY_REGISTRY.keys()),
        default=config.STRATEGIES_TO_RUN,
    )
    parser.add_argument("--models", nargs="+", default=config.MODELS)
    parser.add_argument("--output", type=str, default=config.RESULTS_LOG)
    parser.add_argument("--db", type=str, default=config.DB_PATH)
    parser.add_argument(
        "--db-summary", action="store_true",
        help="Print a summary of all results in the database and exit"
    )
    return parser.parse_args()


def resolve_opponent_types(setting: str) -> list:
    if setting == "both":
        return ["fixed", "cycle"]
    if setting == "all":
        return ["fixed", "cycle", "tft"]
    return [setting]


#  Main 

def main():
    args = parse_args()

    # DB summary mode
    if args.db_summary:
        os.makedirs(os.path.dirname(args.db), exist_ok=True)
        db = Database(args.db)
        db.summary()
        return

    opp_types   = resolve_opponent_types(args.opponent_type)
    start_moves = get_opponents_to_run(args.opponent_move)
    start_time  = datetime.now()

    total_calls = (
        len(args.models) * len(args.strategies)
        * len(opp_types) * len(start_moves) * args.rounds
    )
    # SocialQA makes 2 calls per round
    if "SocialQA" in args.strategies:
        total_calls += len(args.models) * len(opp_types) * len(start_moves) * args.rounds

    print("=" * 65)
    print("  ToM Gap Experiment — RPS Replication")
    print("=" * 65)
    print(f"  Opponent types:  {opp_types}")
    print(f"  Start moves:     {start_moves}")
    print(f"  Rounds:          {args.rounds} per combination")
    print(f"  Models:          {args.models}")
    print(f"  Strategies:      {args.strategies}")
    print(f"  Total API calls: ~{total_calls}")
    print(f"  Database:        {args.db}  (append-only)")
    print("=" * 65)

    # Print the run matrix
    print("\n  Run matrix:")
    for opp_type in opp_types:
        for move in start_moves:
            opp = make_opponent(opp_type, move)
            seq = []
            tmp = make_opponent(opp_type, move)
            for _ in range(5):
                m = tmp.next_move()
                seq.append(m)
                if hasattr(tmp, 'update'):
                    tmp.update('J')  # dummy agent move for display
            print(f"    [{opp.label}]  e.g. round 1-5: {seq}...")
    print()

    if args.rounds >= 50:
        answer = input(f"~{total_calls} API calls. Continue? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    # Main loop 
    raw_results = {}
    avg_results = []

    # Open DB once — save after every completed block so no data is lost
    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    db     = Database(args.db)
    run_id = start_time.strftime("%Y%m%d_%H%M%S")

    for model_id in args.models:
        raw_results[model_id] = {}
        print(f"\n{'━'*65}")
        print(f"  MODEL: {model_id}")
        print(f"{'━'*65}")

        for strat_key in args.strategies:
            if strat_key not in STRATEGY_REGISTRY:
                print(f"  [WARN] Unknown strategy '{strat_key}' — skipping.")
                continue

            raw_results[model_id][strat_key] = {}
            strat_config = STRATEGY_REGISTRY[strat_key]

            for opp_type in opp_types:
                raw_results[model_id][strat_key][opp_type] = {}
                per_type_results = []

                for start_move in start_moves:
                    opponent = make_opponent(opp_type, start_move)
                    print(f"\n  [{strat_key}] vs [{opponent.label}]")

                    result = run_strategy(
                        model_id     = model_id,
                        strat_key    = strat_key,
                        strat_config = strat_config,
                        opponent     = opponent,
                        total_rounds = args.rounds,
                    )

                    raw_results[model_id][strat_key][opp_type][start_move] = result
                    per_type_results.append((start_move, result))

                    # ── Save after EVERY completed block ──────────────────────
                    # One block = one (model x strategy x opponent x start_move)
                    # If interrupted, completed blocks are safe in the DB.
                    block_id = f"{run_id}_{model_id[-10:]}_{strat_key}_{opp_type}_{start_move}"
                    db.save_run(
                        run_id    = block_id,
                        timestamp = start_time.isoformat(),
                        metadata  = {
                            "rounds":         args.rounds,
                            "models":         [model_id],
                            "strategies":     [strat_key],
                            "opponent_types": [opp_type],
                            "start_moves":    [start_move],
                        },
                        raw_results = {
                            model_id: {
                                strat_key: {
                                    opp_type: {start_move: result}
                                }
                            }
                        },
                    )

                averaged = average_results(
                    model_id, strat_key,
                    STRATEGY_REGISTRY[strat_key]["label"],
                    opp_type, per_type_results
                )
                avg_results.append(averaged)

    # Final JSON log 
    save_json(args.output, run_id, start_time, args, opp_types, start_moves,
              raw_results, avg_results)

    #  Summary 
    print_summary(avg_results)
    print(f"\n  Run 'python main.py --db-summary' to see all accumulated results.")


# Averaging 

def average_results(model_id, strat_key, strat_label, opp_type, results_list):
    def mean(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    def stdev(vals):
        vals = [v for v in vals if v is not None]
        return round(statistics.stdev(vals), 4) if len(vals) >= 2 else None

    win_rates = [r["win_rate"]         for _, r in results_list]
    regrets   = [r["delta_functional"] for _, r in results_list]
    delta_toms= [r["delta_tom"]        for _, r in results_list]
    tom_pcts  = [r["tom_pct"]          for _, r in results_list]
    gaps      = [r["gap"]              for _, r in results_list]

    return {
        "model_id":               model_id,
        "strategy":               strat_key,
        "strategy_label":         strat_label,
        "opponent_type":          opp_type,
        "start_moves":            [m for m, _ in results_list],
        "win_rate_mean":          mean(win_rates),
        "win_rate_stdev":         stdev(win_rates),
        "delta_functional_mean":  mean(regrets),
        "delta_functional_stdev": stdev(regrets),
        "delta_tom_mean":         mean(delta_toms),
        "tom_pct_mean":           mean(tom_pcts),
        "gap_mean":               mean(gaps),
        "per_start_move": {
            move: {
                "win_rate":         r["win_rate"],
                "delta_functional": r["delta_functional"],
                "delta_tom":        r["delta_tom"],
                "tom_pct":          r["tom_pct"],
                "gap":              r["gap"],
            }
            for move, r in results_list
        },
    }


# JSON save (append-mode, for visualiser) 
def save_json(output_path, run_id, start_time, args, opp_types, start_moves,
              raw_results, avg_results):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            try:
                log = json.load(f)
            except json.JSONDecodeError:
                log = []
    else:
        log = []

    log.append({
        "run_id":    run_id,
        "timestamp": start_time.isoformat(),
        "metadata": {
            "opponent_types": opp_types,
            "start_moves":    start_moves,
            "rounds":         args.rounds,
            "models":         args.models,
            "strategies":     args.strategies,
        },
        "averaged_results": avg_results,
    })

    with open(output_path, "w") as f:
        json.dump(log, f, indent=2)
    print(f"    JSON log:   {output_path}  ({len(log)} runs)")


# Summary table 

def print_summary(avg_results):
    print()
    print("=" * 82)
    print("  FINAL SUMMARY  (averaged across start moves)")
    print("=" * 82)
    print(
        f"  {'Model':<22} {'OppType':<8} {'Strategy':<12} "
        f"{'Win%':>7} {'±':>5} {'ΔFunc/T':>8} {'ToM%':>6} {'Gap':>8}"
    )
    print(f"  {'-'*79}")

    for opp_type in ["fixed", "cycle", "tft"]:
        rows = [r for r in avg_results if r["opponent_type"] == opp_type]
        if not rows:
            continue
        print(f"  ── {opp_type.upper()} {'─'*55}")
        for r in rows:
            model = r["model_id"].split("/")[-1][:20]
            win   = f"{r['win_rate_mean']:.1f}%"
            sd    = f"±{r['win_rate_stdev']:.1f}" if r["win_rate_stdev"] else "  — "
            reg   = f"{r['delta_functional_mean']:.3f}"
            tom   = f"{r['tom_pct_mean']:.1f}%" if r["tom_pct_mean"] is not None else "  — "
            gap   = f"{r['gap_mean']:+.3f}" if r["gap_mean"] is not None else "  — "
            print(
                f"  {model:<22} {opp_type:<8} {r['strategy']:<12} "
                f"{win:>7} {sd:>5} {reg:>8} {tom:>6} {gap:>8}"
            )

    print("=" * 82)
    print()
    print("  KEY:")
    print("  Win%     = functional ToM — how often model actually won")
    print("  ±        = std deviation across start moves")
    print("  ΔFunc/T  = (optimal−actual)/rounds  (0=perfect, 2=worst)")
    print("  ToM%     = literal ToM prediction accuracy (SocialQA only)")
    print("  Gap      = ΔFunctional − ΔToM (SocialQA) | 100−Win% (Oracle)")
    print()
    print("  FIXED: same move every round")
    print("  CYCLE: J→F→B→J→... repeating")
    print("  TFT:   plays best-response to agent's last move (tit-for-tat)")
    print()


if __name__ == "__main__":
    main()
