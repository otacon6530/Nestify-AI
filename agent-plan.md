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
- If `stream=False`, delegates to a second method (e.g., `generate_sync`) that returns the full summary string.

## Next Steps
- Refactor `Agent` class in agent2.py to follow this plan.
- Add streaming logic to `generate`.
- Implement a separate method (e.g., `generate_sync`) for non-streaming output.
- Update prompts and result handling to prevent hallucinated claims.
- Test with scenarios that previously caused false claims.

## Memory Condensation Method
- Implement a method in the Agent class to pull the latest memory state from the Memory class.
- Condense the memory into a minimal, context-optimized JSON format.
- Return the condensed memory as a string for use in prompts or context windows.
- The method should:
	- Remove redundant or verbose data.
	- Prioritize recent, relevant, and high-value context.
	- Be efficient for use with LLMs and context-limited environments.

## Tool List Condensation Method
- Implement a method in the Agent class to return the available tools and their descriptions.
- Format the tool list and descriptions as a minimal, condensed JSON object.
- Return the JSON as a string for easy injection into LLM context windows.
- The method should:
	- Include only essential tool names and short descriptions.
	- Exclude verbose or redundant metadata.
	- Be optimized for context-limited environments.

## LLM Execution Orchestrator Method
- Implement an orchestrator method in the Agent class to route between different LLM execution modes.
- Modes:
	- **Simple:** For single-turn responses (e.g., "Hello", "Tell me a joke").
	- **Plan:** For multi-step, tool-using, or complex tasks.
- The orchestrator should:
	- Inspect the user request and select the appropriate execution mode.
	- Delegate to the simple or plan method as needed.
	- Return results in a format compatible with streaming or non-streaming output.

## Clarification Method
- Implement a method in the Agent class to clarify and reword user requests using the LLM.
- The method should:
	- Create a plan to gather all necessary information (e.g., list files, inspect resources).
	- Execute tool calls and LLM think steps to collect context.
	- Reword the user request with specific, actionable details for future steps (e.g., replace "all classes" with a list of actual class files).
- This method should be generic and work for any type of request, not just code review or file listing.
- The clarified request should be used for subsequent planning and execution phases.

## Plan Generation Method
- Implement a method in the Agent class to generate a plan after the request is clarified.
- The method should:
	- Take the clarified request as input.
	- Use the LLM to output a structured plan consisting of tool calls and thinking steps.
	- Format the plan as a list of steps, each specifying the action (tool or think) and required arguments.
- The plan should be actionable and ready for execution by the agent.

## Plan Execution Method
- Implement a method in the Agent class to execute the generated plan.
- The method should:
	- Iterate through each step in the plan.
	- Execute tool calls and LLM thinking steps as specified.
	- If any tool call fails (returns an error or exception), abort execution and skip the remaining steps.
	- Log or record the reason for aborting if a failure occurs.
- The method should return the results of executed steps and any error information if applicable.

## Completion Check Method (is_done)
- Implement an `is_done` method in the Agent class to determine if the original request is fully satisfied.
- The method should:
	- Use the LLM to analyze the results of executed steps and the original request.
	- Decide if more actions are necessary to complete the request.
	- Return a boolean (True if done, False if more steps are needed) and optionally a reason or next steps.

## Iterative Planning and Execution Loop
- After each execution, if `is_done` returns False, repeat the planning and execution steps.
- Continue looping until either:
	- The request is fully satisfied (`is_done` returns True), or
	- A maximum execution count is reached (to prevent infinite loops).
- Log or report if the max execution count is hit before completion.

---
(Feel free to add more requirements or details below)
