# Prompt template used by codebuff to solve SWE-bench problems
CODEBUFF_PLANNING_INSTRUCTION = """Please write a detailed plan for solving the problem specified in instructions.md. Write your plan to a file called plan.md. Your plan should include:
1. Analysis of the problem and what needs to be changed
2. Identification of relevant files and code sections
3. Step-by-step implementation strategy
4. Potential risks and how to mitigate them"""

# CODEBUFF_INSTRUCTION = """Please solve the problem specified in instructions.md, using the plan outlined in plan.md. Feel free to run any tests you think will help you solve the problem, but please make sure you're actually making progress on solving the problem. Keep going until you are satisfied with the solution."""
CODEBUFF_INSTRUCTION = """Please solve the problem specified in instructions.md, using the plan outlined in plan.md. Don't run any tests, and keep going until you are satisfied with the solution."""
