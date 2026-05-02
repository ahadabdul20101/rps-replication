
# prompts/__init__.py
# Registry mapping strategy keys to their build/parse functions.


from prompts.qa        import build_prompt as qa_build,        parse_response as qa_parse
from prompts.cot       import build_prompt as cot_build,       parse_response as cot_parse
from prompts.social_qa import build_prompt as social_qa_build, parse_response as social_qa_parse
from prompts.oracle    import build_prompt as oracle_build,    parse_response as oracle_parse

STRATEGY_REGISTRY = {
    "QA": {
        "label": "QA — Direct pick",
        "build": qa_build,
        "parse": qa_parse,
    },
    "CoT": {
        "label": "CoT — Think first",
        "build": cot_build,
        "parse": cot_parse,
    },
    "SocialQA": {
        "label": "Social QA — Predict then act",
        "build": social_qa_build,
        "parse": social_qa_parse,
    },
    "Oracle": {
        "label": "Oracle — Told the answer",
        "build": oracle_build,
        "parse": oracle_parse,
    },
}
