import sqlite3, sys
sys.path.insert(0, '.')
from database import Database

db = Database('results/results.db')

# Simulate a minimal save
fake_result = {
    'strategy_label': 'QA', 'opponent_type': 'cycle-J', 'opponent_start': 'J',
    'total_rounds': 3, 'wins': 1, 'ties': 1, 'loses': 1, 'win_rate': 33.0,
    'delta_functional': 0.9, 'delta_tom': None, 'tom_pct': None, 'gap': None,
    'parse_failures': 0,
    'round_records': [
        {'round': 1, 'model_move': 'F', 'opponent': 'J', 'outcome': 'win',
         'score': 1, 'prediction': None, 'clean_prediction': None,
         'fallback_used': False, 'raw_text': 'Option: F'},
    ]
}

try:
    db.save_run(
        'test_123', '2026-01-01',
        {'rounds': 3, 'models': ['llama3.3-70b-instruct'],
         'strategies': ['QA'], 'opponent_types': ['cycle'], 'start_moves': ['J']},
        {'llama3.3-70b-instruct': {'QA': {'cycle': {'J': fake_result}}}}
    )
    print('Save worked!')
except Exception as e:
    print(f'Save FAILED: {e}')
    import traceback
    traceback.print_exc()