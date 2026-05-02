import sqlite3

SOURCE = "results/results.db"
TARGET = "results/cycle.db"

src = sqlite3.connect(SOURCE)
tgt = sqlite3.connect(TARGET)

# Copy schema
for line in src.iterdump():
    if line.startswith("CREATE"):
        try:
            tgt.execute(line)
        except:
            pass

# Copy only clean 100-round blocks
run_ids = src.execute("""
    SELECT DISTINCT run_id FROM results
    WHERE total_rounds = 100
    AND parse_failures = 0
""").fetchall()
run_ids = [r[0] for r in run_ids]

print(f"Copying {len(run_ids)} clean runs...")

for run_id in run_ids:
    # runs table
    row = src.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if row:
        tgt.execute("INSERT OR IGNORE INTO runs VALUES ({})".format(
            ",".join(["?"]*len(row))), row)

    # results table
    rows = src.execute("SELECT * FROM results WHERE run_id=?", (run_id,)).fetchall()
    for row in rows:
        tgt.execute("INSERT OR IGNORE INTO results VALUES ({})".format(
            ",".join(["?"]*len(row))), row)

    # round_records table
    rows = src.execute("SELECT * FROM round_records WHERE run_id=?", (run_id,)).fetchall()
    for row in rows:
        tgt.execute("INSERT OR IGNORE INTO round_records VALUES ({})".format(
            ",".join(["?"]*len(row))), row)

tgt.commit()

print(f"Done. cycle.db contents:")
for table in ["runs","results","round_records"]:
    count = tgt.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {count} rows")

print()
rows = tgt.execute("""
    SELECT model_id, strategy, opponent_type, win_rate, tom_pct, gap
    FROM results ORDER BY model_id, strategy, opponent_type
""").fetchall()
for r in rows:
    print(f"  {r[0][-20:]:<22} {r[1]:<10} {r[2]:<14} win={r[3]} tom={r[4]} gap={r[5]}")