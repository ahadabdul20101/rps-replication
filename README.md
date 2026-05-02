# RPS Theory of Mind Gap Replication

This project replicates and extends the Rock-Paper-Scissors experiment from Riemer et al. (2025), "Theory of Mind Benchmarks are Broken for Large Language Models" (arXiv 2403.14859). The original paper tested base language models and found a gap between literal Theory of Mind (predicting what an opponent will do) and functional Theory of Mind (acting on that prediction to win). This replication tests whether the same gap exists in instruction fine-tuned models and whether structured prompting can bridge it.

## Research Question

Can structured prompting strategies close the gap between knowing what an opponent will do and acting on that knowledge, in instruction fine-tuned LLMs? And how does this compare to the findings on base models in the original paper?

## Key Findings

Instruction fine-tuned models show a clear and measurable Theory of Mind gap. Social QA prompting (predicting then acting in two separate API calls) nearly eliminates the gap on deterministic cycle opponents, raising win rates from approximately 28% to 87% for GPT-4o and 90% for Llama 3.3 70B. However, tit-for-tat opponents cause a complete collapse of literal ToM accuracy to near-random levels (36%) for both models regardless of prompting strategy, with functional ToM remaining intact. This suggests the failure on tit-for-tat is in prediction rather than application, and is caused by the self-referential nature of the opponent rather than an instruction tuning artifact.

A notable model-specific finding is that Llama 3.3 70B has a substantially larger Oracle gap than GPT-4o (+20pp vs +4pp on cycle opponents), meaning Llama fails to apply explicitly provided information more often than GPT-4o even when no prediction is required.

## Differences from the Original Paper

The original paper tested base models (Mixtral-8x7B, LLaMA-2 70B) using logprob-based prompting, where the model scores complete sentences rather than generating text. This replication uses instruction fine-tuned models (GPT-4o, Llama 3.3 70B Instruct) accessed via the Azure OpenAI API, with chat-based generation prompts instead of logprob completion. This difference is intentional: instruction fine-tuned models are the most commonly deployed and studied variants, and understanding their ToM gap has direct practical relevance.

This project also introduces a cycle opponent (J to F to B repeating every 3 rounds) as a novel extension beyond the fixed and tit-for-tat opponents in the original paper. The cycle opponent sits between fixed (trivial) and tit-for-tat (requires self-modelling) in difficulty, and allows isolation of external pattern detection as a cognitive demand.

## Prompting Strategies

**QA** — The model sees the full game history and picks a move directly. No reasoning is elicited. Serves as the baseline condition for functional ToM.

**CoT** — Chain of thought. The model is asked to reason step by step before choosing. Reasoning is written out explicitly and the final answer appears on a separately labelled line.

**Social QA** — Two API calls per round. Call 1 asks the model to predict the opponent's next move given the history. Call 2 receives that prediction verbatim and asks for the action. This separates literal ToM (prediction accuracy, measured as ToM%) from functional ToM (win rate) in the same round.

**Oracle** — The model is told the opponent's exact move before choosing. Any loss is a direct failure to apply explicitly given information. The gap equals 100 minus Win%.

## Opponent Types

**Fixed** — Plays the same move every round. Detectable in one round.

**Cycle** — Rotates J to F to B repeating every 3 rounds. Fully detectable after 3 rounds. Novel extension over the source paper.

**Tit-for-Tat** — Plays the best response to the agent's own last move. Requires self-modelling to predict: the agent must reason about its own causal role in determining the opponent's behaviour.

## Action Labels

Rock, Paper, Scissors are replaced with neutral labels J, F, B throughout. This avoids pretraining contamination: LLMs have seen vast amounts of RPS strategy text during training and already know Rock beats Scissors. Neutral labels force the model to learn the payoff structure purely from the table provided in the system prompt, ensuring pattern detection is tested rather than recall of prior knowledge. J beats B, F beats J, B beats F.

## Models

GPT-4o (Azure OpenAI, Sweden Central deployment) and Llama 3.3 70B Instruct (Azure AI Foundry, same resource). Both are instruction fine-tuned variants. All experiments run at temperature 1.0, 100 rounds per condition, averaged across start moves J, F, and B where multiple are available.

## Metrics

**Win%** — How often the model won. Optimal play achieves 100%. Random play achieves approximately 33%.

**DeltaFunctional/T** — Regret per step. (Optimal cumulative score minus actual cumulative score) divided by T. Scores are +1 win, 0 tie, -1 loss. Lower is better. 0 is perfect play, 2 is the worst possible.

**ToM%** — Prediction accuracy. Measured for Social QA only. How often the model correctly predicted the opponent's next move. Random prediction yields 33%.

**Gap** — For Oracle: 100 minus Win%. For Social QA: DeltaFunctional/T minus DeltaToM/T, where DeltaToM/T is the regret the model would have incurred if it always played the best response to its own prediction. A gap near zero means the model acts consistently with what it predicts. A large positive gap means the model knows what the opponent will do but fails to act on it.

## Results

Clean results are in the results folder:

`results/results_azure_4o.db` — GPT-4o, all conditions complete, 33 blocks

`results/results_azure_llama.db` — Llama 3.3 70B, all conditions complete, 34 blocks

`results/results_gpt4o.xlsx` — GPT-4o results with summary, all blocks, and round records sheets

`results/results_llama.xlsx` — Llama results with summary, all blocks, and round records sheets

## Project Structure

```
RPS_replication/
    config.py               API keys and experiment settings (not pushed to git)
    config_template.py      Template showing required config keys
    game.py                 Game rules, payoff table, opponent classes
    api_client.py           Azure API routing for GPT-4o and Llama
    runner.py               Round loop, per-round DB save, strategy dispatch
    main.py                 Entry point, nested loop over all conditions
    database.py             SQLite schema and save functions
    check_progress.py       Monitor DB during a run
    make_cycle_db.py        Extracts clean blocks into a separate DB
    Docs/
        ToM_Preliminary_v2.docx
    prompts/
        __init__.py         Strategy registry
        qa.py               Direct pick prompt
        cot.py              Chain of thought prompt
        social_qa.py        Two-call predict then act prompt
        oracle.py           Told the answer prompt
    results/
        results_azure_4o.db     Clean GPT-4o results
        results_azure_llama.db  Clean Llama results
        results_gpt4o.xlsx      GPT-4o Excel export
        results_llama.xlsx      Llama Excel export
```

## Planned Extensions

Logprob-based prompting (LM Prompting, Figure 3 of the source paper) will be added in a separate module (RPS_logprob). This approach scores three complete sentences (one per candidate move) and takes the argmax probability rather than generating text. It allows direct comparison between chat-based and logprob-based literal ToM measurement, and tests whether the ToM failures observed here are genuine cognitive limitations or verbalization artifacts introduced by instruction tuning.

## Setup

Copy config_template.py to config.py and fill in your Azure API keys.

```bash
pip install openai httpx
python main.py --rounds 100 --strategies QA CoT SocialQA Oracle --opponent-type all --opponent-move all --models gpt-4o
```

## Reference

Riemer, M., et al. (2025). Theory of Mind Benchmarks are Broken for Large Language Models. arXiv:2403.14859.
