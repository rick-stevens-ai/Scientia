import sys
import openai
from typing import List, Dict, Any

##############################################################################
# Configuration: Set your OpenAI API credentials and model information here
##############################################################################

#OPENAI_API_KEY = "sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
#MODEL_ENDPOINT = "https://api.openai.com/v1/chat/completions"  # Default endpoint
#MODEL_ID       = "gpt-4"  # Or whichever model you prefer

OPENAI_API_KEY = "CELS"  # <--- Replace with your actual key

MODEL_ENDPOINT = "http://195.88.24.64:80/v1"
MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

openai.api_key = OPENAI_API_KEY
# If using a custom endpoint, you can configure it like:
openai.api_base = MODEL_ENDPOINT


##############################################################################
# Agent Prompts
##############################################################################

def get_supervisor_agent_prompt():
    """
    The Supervisor Agent’s primary responsibility is to read the scientist’s
    overall research goal, break it down into tasks, and orchestrate the
    workflow among the specialized agents.
    """
    return (
        "You are the Supervisor Agent in a multi-agent AI co-scientist system. "
        "You receive the high-level research goal and coordinate a series of "
        "agents (Generation, Reflection, Ranking, Evolution, Proximity Check, "
        "Meta-review) to iteratively produce, refine, and rank scientific ideas. "
        "Manage the overall workflow and produce final instructions or summaries "
        "to the user. Keep track of each round, pass the correct context to each "
        "agent, and store or update the system's memory as needed."
    )

def get_generation_agent_prompt():
    """
    The Generation Agent explores the literature, brainstorms, and synthesizes
    new ideas or hypotheses, ensuring that each idea explicitly states a hypothesis.
    """
    return (
        "You are the Generation Agent in a multi-agent AI co-scientist system. "
        "You produce new ideas and hypotheses in response to a defined "
        "research goal. For each idea, you MUST include an explicit hypothesis "
        "statement. Leverage existing literature, domain knowledge, and "
        "creative thinking to propose multiple distinct research directions, "
        "frameworks, or experimental designs. Strive for novelty, practicality, "
        "and scientific rigor."
    )

def get_reflection_agent_prompt():
    """
    The Reflection Agent reviews proposals for potential flaws, inconsistency,
    and feasibility, and specifically evaluates each hypothesis for plausibility,
    novelty, and likelihood of being correct.
    """
    return (
        "You are the Reflection Agent in a multi-agent AI co-scientist system. "
        "You critically analyze each proposed idea and its hypothesis. For each, "
        "evaluate plausibility, novelty, potential flaws, and likelihood of being correct. "
        "Recommend improvements or missing angles, and highlight strengths and weaknesses "
        "so that subsequent agents can refine the ideas further."
    )

def get_ranking_agent_prompt():
    """
    The Ranking Agent compares and ranks competing hypotheses or proposals,
    often via a debate or tournament approach, taking into account each idea's
    hypothesis plausibility, novelty, and correctness likelihood.
    """
    return (
        "You are the Ranking Agent in a multi-agent AI co-scientist system. "
        "You receive multiple research ideas or proposals, each containing an explicit "
        "hypothesis. Your job is to compare them, simulate a debate about their merits, "
        "and rank them from most to least promising. In the rationale, highlight: "
        "(1) Hypothesis plausibility, (2) Novelty, and (3) Likelihood of correctness. "
        "Use these criteria to produce a final ranking."
    )

def get_evolution_agent_prompt():
    """
    The Evolution Agent modifies existing ideas by simplifying or extending them,
    combining them with other concepts, etc. Each refined idea must still contain
    an explicit hypothesis statement.
    """
    return (
        "You are the Evolution Agent in a multi-agent AI co-scientist system. "
        "You take an existing set of research ideas (each with a hypothesis) and "
        "refine or evolve them. You may simplify complex designs, combine ideas, "
        "or extend them into new directions, but each refined idea must retain an "
        "explicit hypothesis. Highlight key changes so the ideas become stronger, "
        "more innovative, or more feasible."
    )

def get_proximity_check_agent_prompt():
    """
    The Proximity Check Agent ensures that new proposals stay within the required
    constraints and remain relevant to the original research goal.
    """
    return (
        "You are the Proximity Check Agent in a multi-agent AI co-scientist system. "
        "Your role is to evaluate whether newly generated or revised ideas stay "
        "aligned with the assigned research goal, meet ethical and feasibility "
        "constraints, and do not drift too far from the desired objectives. If "
        "misalignment is detected, provide warnings and corrective suggestions."
    )

def get_meta_review_agent_prompt():
    """
    The Meta-review Agent synthesizes the top-ranked ideas into a cohesive
    overview and final recommendation, focusing on only the best proposals.
    """
    return (
        "You are the Meta-review Agent in a multi-agent AI co-scientist system. "
        "You take the final set of refined, top-ranked research proposals (only "
        "the top 5 in the final ranking) and compose a meta-analysis: summarize "
        "the core ideas, discuss strengths and limitations, and suggest practical "
        "next steps. Provide a concise but comprehensive overview."
    )

##############################################################################
# Helper function to call an agent via the OpenAI ChatCompletion API
##############################################################################

def call_agent(
    agent_system_prompt: str,
    user_prompt: str,
    additional_context: str = ""
) -> str:
    """
    Given an agent-specific system prompt, a user-level prompt, and optional
    additional context (e.g., lists of ideas, feedback from other agents), call
    the OpenAI ChatCompletion API to get the agent's response.
    """
    messages = [
        {"role": "system", "content": agent_system_prompt},
    ]

    if additional_context:
        messages.append({"role": "assistant", "content": additional_context})

    messages.append({"role": "user", "content": user_prompt})

    response = openai.ChatCompletion.create(
        model=MODEL_ID,
        messages=messages
    )

    return response["choices"][0]["message"]["content"]

##############################################################################
# Main multi-round workflow function
##############################################################################

def run_co_scientist_workflow(
    research_goal: str,
    num_ideas: int = 10,
    num_rounds: int = 3
) -> None:
    """
    This function orchestrates a multi-round AI co-scientist workflow:
      1) The Supervisor Agent sets up the initial tasks.
      2) Generation (or Evolution in subsequent rounds) Agent produces ideas,
         each with an explicit hypothesis.
      3) Reflection Agent reviews and evaluates hypotheses.
      4) Proximity Check Agent ensures alignment/feasibility.
      5) Ranking Agent ranks them.
      6) Remove the weaker proposals in each round (lower half, third, quarter...)
         and replace them with newly generated ideas.
      7) After the final round, the Meta-review Agent generates a final overview,
         presenting only the top 5 proposals.
    """
    # Supervisor welcomes and sets the stage
    supervisor_intro = call_agent(
        get_supervisor_agent_prompt(),
        user_prompt=(
            f"The user has the research goal: '{research_goal}'. "
            "We will conduct multiple rounds of idea generation and refinement, "
            "ensuring each idea has an explicit hypothesis. We will remove weaker "
            "proposals each round and replace them. Eliminated proposals must not "
            "reappear in subsequent rounds."
        )
    )
    print("=== SUPERVISOR INTRO ===")
    print(supervisor_intro)
    print("")

    # Keep track of the ideas across rounds
    ideas: List[str] = []
    excluded_ideas: List[str] = []  # Track eliminated ideas so they do not reappear

    # Define the fraction of ideas to remove each round
    removal_fractions = [0.5, 1/3, 0.25]

    for round_idx in range(num_rounds):
        print(f"\n========== ROUND {round_idx+1} / {num_rounds} ==========\n")

        # 1) Generate or Evolve Ideas
        if round_idx == 0:
            # First round, generate new ideas
            gen_prompt = (
                f"Please generate {num_ideas} distinct research ideas or hypotheses "
                f"for the goal: '{research_goal}'. For each idea, include an explicit "
                f"hypothesis. Avoid any ideas that are in this excluded list: {excluded_ideas}."
            )
            generation_output = call_agent(
                get_generation_agent_prompt(),
                user_prompt=gen_prompt
            )
            ideas = parse_ideas_from_text(generation_output, expected_count=num_ideas)
            print("=== GENERATION AGENT OUTPUT ===")
            print(generation_output)
            print("")
        else:
            # In subsequent rounds, we first remove the weakest proposals, then refine
            # existing ones, then generate new ones to replace the removed ones.

            # Evolve existing ideas
            print("=== EVOLUTION AGENT OUTPUT (Refining Existing Ideas) ===")
            ideas_text = "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(ideas)])
            evolve_prompt = (
                f"We have the following {len(ideas)} ideas:\n\n"
                f"{ideas_text}\n\n"
                "Please refine or evolve each idea to be stronger, more novel, or more feasible. "
                "Each must retain an explicit hypothesis. Avoid introducing any idea that's in "
                f"this excluded list: {excluded_ideas}."
            )
            evolution_output = call_agent(
                get_evolution_agent_prompt(),
                user_prompt=evolve_prompt
            )
            evolved_ideas = parse_ideas_from_text(
                evolution_output,
                expected_count=len(ideas)
            )
            print(evolution_output)
            print("")

            ideas = evolved_ideas

        # 2) Reflect on the ideas
        ideas_text = "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(ideas)])
        reflection_prompt = (
            f"Please analyze these {len(ideas)} ideas, each with its hypothesis, "
            "for plausibility, novelty, potential flaws, and likelihood of being correct:\n\n"
            + ideas_text
        )
        reflection_output = call_agent(
            get_reflection_agent_prompt(),
            user_prompt=reflection_prompt
        )
        print("=== REFLECTION AGENT OUTPUT ===")
        print(reflection_output)
        print("")

        # 3) Proximity Check
        proximity_prompt = (
            f"Please ensure these ideas remain aligned with the research goal '{research_goal}' "
            "and check for ethical, feasibility, or scope concerns. If any are out of scope, "
            "suggest modifications or indicate if they should be dropped:\n\n" + ideas_text
        )
        proximity_output = call_agent(
            get_proximity_check_agent_prompt(),
            user_prompt=proximity_prompt
        )
        print("=== PROXIMITY CHECK AGENT OUTPUT ===")
        print(proximity_output)
        print("")

        # 4) Ranking
        ranking_prompt = (
            f"We have these {len(ideas)} ideas:\n\n{ideas_text}\n\n"
            "Please rank them from most promising to least promising, "
            "considering (1) Hypothesis plausibility, (2) Novelty, and "
            "(3) Likelihood of correctness. Provide a rationale."
        )
        ranking_output = call_agent(
            get_ranking_agent_prompt(),
            user_prompt=ranking_prompt
        )
        print("=== RANKING AGENT OUTPUT ===")
        print(ranking_output)
        print("")

        # Reorder `ideas` by the ranking
        ideas_ordered = parse_ideas_order_from_ranking(ranking_output, ideas)
        ideas = ideas_ordered

        # Remove the weaker proposals based on the fraction for the current round
        fraction = removal_fractions[round_idx] if round_idx < len(removal_fractions) else 0.25
        num_to_remove = int(len(ideas) * fraction)
        if num_to_remove < 1 and len(ideas) > 1:
            num_to_remove = 1

        if num_to_remove > 0:
            removed_ideas = ideas[-num_to_remove:]  # take from the bottom
            ideas = ideas[:-num_to_remove]
            excluded_ideas.extend(removed_ideas)

            # Generate new ideas to replace them
            gen_prompt = (
                f"Please generate {num_to_remove} new distinct research ideas. Each must include "
                "an explicit hypothesis, and they must not reintroduce or duplicate any in this "
                f"excluded list: {excluded_ideas}. The research goal is: '{research_goal}'."
            )
            new_generation_output = call_agent(
                get_generation_agent_prompt(),
                user_prompt=gen_prompt
            )
            new_ideas = parse_ideas_from_text(new_generation_output, expected_count=num_to_remove)
            ideas.extend(new_ideas)

            print("=== REMOVING WEAKER PROPOSALS ===")
            print(f"We removed {num_to_remove} ideas (the weakest):")
            for idx, removed in enumerate(removed_ideas):
                print(f"- {removed}")
            print("\n=== GENERATION AGENT OUTPUT (Replacement Ideas) ===")
            print(new_generation_output)
            print("")

        # Supervisor summary of the round
        round_summary = call_agent(
            get_supervisor_agent_prompt(),
            user_prompt=(
                f"Summarize the results of round {round_idx+1}, referencing the Reflection, "
                f"Proximity Check, and Ranking. The final set of ideas (after removal/replacement) "
                f"are:\n\n"
                + "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(ideas)])
            )
        )
        print("=== SUPERVISOR ROUND SUMMARY ===")
        print(round_summary)

    # After all rounds, do a final ranking and then a Meta-review of only the top 5
    ideas_text = "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(ideas)])
    final_ranking_prompt = (
        f"Before the final Meta-review, please rank these {len(ideas)} ideas again, "
        "from most promising to least promising, to ensure we present the top 5. "
        "Focus on (1) Hypothesis plausibility, (2) Novelty, and (3) Likelihood of correctness.\n\n"
        + ideas_text
    )
    final_ranking_output = call_agent(
        get_ranking_agent_prompt(),
        user_prompt=final_ranking_prompt
    )
    print("\n=== FINAL RANKING AGENT OUTPUT ===")
    print(final_ranking_output)

    # Reorder `ideas` by the final ranking
    final_ideas_ordered = parse_ideas_order_from_ranking(final_ranking_output, ideas)
    ideas = final_ideas_ordered

    # Keep only top 5
    top_5_ideas = ideas[:5]

    # Meta-review on only the top 5
    final_ideas_text = "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(top_5_ideas)])
    meta_prompt = (
        f"Here are the final top {len(top_5_ideas)} ideas from the iterative process:\n\n"
        f"{final_ideas_text}\n\n"
        "Please provide a meta-review, summarizing the best ideas, their strengths "
        "and weaknesses, and suggest next steps for the scientist."
    )
    meta_review_output = call_agent(
        get_meta_review_agent_prompt(),
        user_prompt=meta_prompt
    )
    print("\n=== META-REVIEW AGENT OUTPUT (TOP 5 ONLY) ===")
    print(meta_review_output)

##############################################################################
# Simple Parsers for Idea Lists and Rankings
##############################################################################

def parse_ideas_from_text(text: str, expected_count: int) -> List[str]:
    """
    Very naive parser to try to split the text into 'expected_count' ideas.
    In a real system, you'd want a more robust approach.
    """
    lines = text.split("\n")
    lines = [ln.strip() for ln in lines if ln.strip()]

    ideas = []
    current_idea = []
    for line in lines:
        if is_new_idea_start(line):
            # If we have a current_idea in progress, push it
            if current_idea:
                ideas.append(" ".join(current_idea).strip())
                current_idea = []
            current_idea.append(line)
        else:
            current_idea.append(line)

    if current_idea:
        ideas.append(" ".join(current_idea).strip())

    # Clamp to expected_count if needed
    if len(ideas) > expected_count:
        ideas = ideas[:expected_count]

    cleaned_ideas = [remove_leading_number(idea).strip() for idea in ideas]

    return cleaned_ideas

def parse_ideas_order_from_ranking(ranking_output: str, current_ideas: List[str]) -> List[str]:
    """
    A naive approach to reorder `current_ideas` based on the Ranking Agent output.
    Attempt to detect numeric order from the ranking output text.
    """
    new_order = []
    lines = ranking_output.split("\n")
    idea_map = {i+1: current_ideas[i] for i in range(len(current_ideas))}

    for line in lines:
        line_stripped = line.strip()
        if line_stripped and line_stripped[0].isdigit():
            # e.g. "1. Idea about X"
            idx_str = line_stripped.split(".")[0].strip()
            try:
                idx = int(idx_str)
                if idx in idea_map and idea_map[idx] not in new_order:
                    new_order.append(idea_map[idx])
            except ValueError:
                pass

    # Append any missing ideas in the original order
    for i in range(len(current_ideas)):
        if idea_map[i+1] not in new_order:
            new_order.append(idea_map[i+1])

    return new_order

def is_new_idea_start(line: str) -> bool:
    line_stripped = line.strip()
    if len(line_stripped) < 2:
        return False
    if line_stripped[0].isdigit() and line_stripped[1] in [".", ")"]:
        return True
    if line_stripped.startswith("- "):
        return True
    return False

def remove_leading_number(text: str) -> str:
    import re
    return re.sub(r'^\s*\d+[\.\)]\s*', '', text).strip()

##############################################################################
# Run the workflow from a command-line argument
##############################################################################

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python co_scientist.py <research_goal>")
        sys.exit(1)

    user_research_goal = ' '.join(sys.argv[1:])  # Combine all args into one string
    run_co_scientist_workflow(
        research_goal=user_research_goal,
        num_ideas=10,   # Default number of ideas per round
        num_rounds=3    # Default number of iterative rounds
    )
