# Agent2.py Redesign Plan

## Goals
- Prevent LLM from hallucinating actions/results.
- Enforce strict separation between planned actions and executed actions.
- Support streaming of final results in the `generate` method.

## Design Principles
1. **Action-First, Response-After:**
	- LLM generates a plan (list of steps).
	- Agent executes each step and records actual results.
	- Only after execution, LLM summarizes what truly happened.

2. **Streaming Support:**
	- The `generate` method should yield tokens or chunks of the final summary, not just return a string.
	- If streaming is enabled, results are sent incrementally as they are produced.

3. **Prompt Injection of Real Results:**
	- After actions are executed, inject the actual results into the summary prompt for the LLM.
	- Example: "Actions performed: [results]. Summarize for the user."

4. **Instructional Guardrails:**
	- Prompts must instruct the LLM: "Only describe actions that were actually performed. Do not claim success unless confirmed."

## Proposed `generate` Method
- Accepts `text` and `stream` (bool) arguments.
- Runs planning, execution, and summary phases.
- If `stream=True`, yields tokens/chunks of the summary as they are generated.
- If `stream=False`, returns the full summary string.

## Next Steps
- Refactor `Agent` class in agent2.py to follow this plan.
- Add streaming logic to `generate`.
- Update prompts and result handling to prevent hallucinated claims.
- Test with scenarios that previously caused false claims.

---
(Feel free to add more requirements or details below)
