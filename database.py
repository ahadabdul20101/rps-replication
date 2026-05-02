#                         made with claude
# =============================================================================
# database.py
# SQLite storage for experiment results.
#
# Schema:
#   runs          — one row per main.py invocation
#   results       — one row per (run × model × strategy × opponent)
#   round_records — one row per round with full diagnostics
#
# round_records diagnostic columns (new):
#   prediction_correct     — did prediction match actual opponent move?
#   action_was_counter     — did model play BEATS[prediction]? (rational)
#   action_was_optimal     — did model play BEATS[opponent_move]? (perfect)
#   fallback_used          — did Call 1 fail and we fell back to QA? (SocialQA)
# =============================================================================

import sqlite3
import json


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript("""

            CREATE TABLE IF NOT EXISTS runs (
                run_id          TEXT PRIMARY KEY,
                timestamp       TEXT,
                rounds          INTEGER,
                models          TEXT,
                strategies      TEXT,
                opponent_types  TEXT,
                start_moves     TEXT
            );

            CREATE TABLE IF NOT EXISTS results (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id           TEXT,
                model_id         TEXT,
                strategy         TEXT,
                strategy_label   TEXT,
                opponent_type    TEXT,
                opponent_start   TEXT,
                total_rounds     INTEGER,
                wins             INTEGER,
                ties             INTEGER,
                loses            INTEGER,
                win_rate         REAL,
                delta_functional REAL,
                delta_tom        REAL,
                tom_pct          REAL,
                gap              REAL,
                parse_failures   INTEGER,
                fallback_rounds  INTEGER,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS round_records (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id                TEXT,
                model_id              TEXT,
                strategy              TEXT,
                opponent_type         TEXT,
                round_num             INTEGER,
                model_move            TEXT,
                opponent_move         TEXT,
                outcome               TEXT,
                score                 INTEGER,
                -- Prediction columns (SocialQA only, NULL for others)
                prediction            TEXT,
                clean_prediction      TEXT,
                -- Diagnostic flags
                prediction_correct    INTEGER,  -- 1/0/NULL
                action_was_counter    INTEGER,  -- 1/0/NULL (counter to prediction)
                action_was_optimal    INTEGER,  -- 1/0 (counter to actual opponent)
                fallback_used         INTEGER,  -- 1/0 (SocialQA only)
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );

            """)

    def save_run(self, run_id: str, timestamp: str, metadata: dict, raw_results: dict):
        """Save a complete run. Appends — never overwrites."""

        BEATS = {'J': 'F', 'F': 'B', 'B': 'J'}

        with self._connect() as conn:

            # ── runs ──────────────────────────────────────────────────────────
            conn.execute("""
                INSERT OR REPLACE INTO runs
                (run_id, timestamp, rounds, models, strategies, opponent_types, start_moves)
                VALUES (?,?,?,?,?,?,?)
            """, (
                run_id, timestamp, metadata["rounds"],
                json.dumps(metadata["models"]),
                json.dumps(metadata["strategies"]),
                json.dumps(metadata["opponent_types"]),
                json.dumps(metadata["start_moves"]),
            ))

            # ── results + round_records ───────────────────────────────────────
            for model_id, model_data in raw_results.items():
                for strat_key, strat_data in model_data.items():
                    for opp_type, type_data in strat_data.items():
                        for start_move, result in type_data.items():

                            # Count fallback rounds
                            fallback_rounds = sum(
                                1 for r in result.get("round_records", [])
                                if r.get("fallback_used")
                            )

                            # results row
                            conn.execute("""
                                INSERT INTO results
                                (run_id, model_id, strategy, strategy_label,
                                 opponent_type, opponent_start, total_rounds,
                                 wins, ties, loses, win_rate, delta_functional,
                                 delta_tom, tom_pct, gap, parse_failures,
                                 fallback_rounds)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """, (
                                run_id, model_id, strat_key,
                                result["strategy_label"],
                                result["opponent_type"],
                                result["opponent_start"],
                                result["total_rounds"],
                                result["wins"], result["ties"], result["loses"],
                                result["win_rate"],
                                result["delta_functional"],
                                result.get("delta_tom"),
                                result.get("tom_pct"),
                                result.get("gap"),
                                result["parse_failures"],
                                fallback_rounds,
                            ))

                            # round_records rows
                            for r in result.get("round_records", []):
                                pred     = r.get("clean_prediction") or r.get("prediction")
                                opp_move = r["opponent"]
                                mdl_move = r["model_move"]

                                # Compute diagnostic flags
                                pred_correct   = None
                                action_counter = None
                                if pred is not None:
                                    pred_correct   = int(pred == opp_move)
                                    action_counter = int(mdl_move == BEATS[pred])

                                action_optimal = int(mdl_move == BEATS[opp_move])
                                fallback_used  = int(r.get("fallback_used", False))

                                conn.execute("""
                                    INSERT INTO round_records
                                    (run_id, model_id, strategy, opponent_type,
                                     round_num, model_move, opponent_move, outcome,
                                     score, prediction, clean_prediction,
                                     prediction_correct, action_was_counter,
                                     action_was_optimal, fallback_used)
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                                """, (
                                    run_id, model_id, strat_key,
                                    result["opponent_type"],
                                    r["round"],
                                    mdl_move, opp_move,
                                    r["outcome"], r["score"],
                                    r.get("prediction"),
                                    r.get("clean_prediction"),
                                    pred_correct,
                                    action_counter,
                                    action_optimal,
                                    fallback_used,
                                ))

        print(f"\n  ✓ Saved to: {self.db_path}")
        self._print_stats()

    def _print_stats(self):
        with self._connect() as conn:
            runs    = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            results = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            rounds  = conn.execute("SELECT COUNT(*) FROM round_records").fetchone()[0]
        print(f"    DB: {runs} runs | {results} result rows | {rounds} round records")

    def query(self, sql: str, params=()):
        """Run a raw SQL query, return list of dicts."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def summary(self):
        """Print human-readable summary of all results."""
        rows = self.query("""
            SELECT
                model_id,
                strategy,
                opponent_type,
                COUNT(*)                       as n_runs,
                ROUND(AVG(win_rate),1)         as avg_win,
                ROUND(AVG(delta_functional),3) as avg_regret,
                ROUND(AVG(tom_pct),1)          as avg_tom,
                ROUND(AVG(gap),3)              as avg_gap,
                SUM(fallback_rounds)           as total_fallbacks
            FROM results
            GROUP BY model_id, strategy, opponent_type
            ORDER BY strategy, opponent_type
        """)

        if not rows:
            print("  No results in database yet.")
            return

        print()
        print("=" * 95)
        print("  DATABASE SUMMARY")
        print("=" * 95)
        print(f"  {'Model':<18} {'Strategy':<12} {'Opponent':<12} {'N':<4} "
              f"{'Win%':>6} {'Regret':>8} {'ToM%':>6} {'Gap':>8} {'Fallbacks':>10}")
        print(f"  {'-'*91}")

        for r in rows:
            model     = (r['model_id'] or '').split('/')[-1][:16]
            tom       = f"{r['avg_tom']:.1f}%"   if r['avg_tom']  is not None else "  —  "
            gap       = f"{r['avg_gap']:+.3f}"   if r['avg_gap']  is not None else "  —  "
            fallbacks = str(r['total_fallbacks']) if r['total_fallbacks'] else "0"
            print(
                f"  {model:<18} {r['strategy']:<12} {r['opponent_type']:<12} "
                f"{r['n_runs']:<4} {r['avg_win']:>5.1f}% {r['avg_regret']:>8.3f} "
                f"{tom:>6} {gap:>8} {fallbacks:>10}"
            )
        print("=" * 95)

    def gap_analysis(self):
        """
        Print the core ToM gap analysis for SocialQA rounds.
        Shows: correct predictions, rational actions, optimal actions.
        """
        rows = self.query("""
            SELECT
                opponent_type,
                COUNT(*)                                    as total_rounds,
                SUM(prediction_correct)                    as pred_correct,
                SUM(action_was_counter)                    as acted_rational,
                SUM(action_was_optimal)                    as acted_optimal,
                SUM(fallback_used)                         as fallbacks,
                -- rounds where knew but didn't act optimally
                SUM(CASE WHEN prediction_correct=1
                          AND action_was_optimal=0
                     THEN 1 ELSE 0 END)                    as knew_but_failed,
                -- rounds where prediction wrong but action happened to be right
                SUM(CASE WHEN prediction_correct=0
                          AND action_was_optimal=1
                     THEN 1 ELSE 0 END)                    as wrong_but_won
            FROM round_records
            WHERE strategy = 'SocialQA'
            AND prediction IS NOT NULL
            GROUP BY opponent_type
            ORDER BY opponent_type
        """)

        if not rows:
            print("  No SocialQA rounds in database.")
            return

        print()
        print("=" * 80)
        print("  SOCIALQA GAP ANALYSIS")
        print("=" * 80)
        print(f"  {'Opponent':<14} {'Total':<7} {'ToM%':>6} {'Counter%':>9} "
              f"{'Optimal%':>9} {'KnewButFailed':>14} {'WrongButWon':>12}")
        print(f"  {'-'*76}")

        for r in rows:
            t    = r['total_rounds']
            tom  = f"{r['pred_correct']/t*100:.1f}%"  if r['pred_correct']  is not None else "—"
            ctr  = f"{r['acted_rational']/t*100:.1f}%" if r['acted_rational'] is not None else "—"
            opt  = f"{r['acted_optimal']/t*100:.1f}%"
            kbf  = str(r['knew_but_failed'])
            wbw  = str(r['wrong_but_won'])
            print(
                f"  {r['opponent_type']:<14} {t:<7} {tom:>6} {ctr:>9} "
                f"{opt:>9} {kbf:>14} {wbw:>12}"
            )
        print("=" * 80)
        print()
        print("  ToM%      = prediction accuracy (literal ToM)")
        print("  Counter%  = played BEATS[own prediction] (rational action)")
        print("  Optimal%  = played BEATS[actual opponent move] (perfect action)")
        print("  KnewButFailed = predicted correctly but didn't play optimal")
        print("  WrongButWon   = predicted wrong but played optimal anyway")
