import sys
import time
import textwrap
from openai import OpenAI
from openai import APIError, APITimeoutError, APIConnectionError, RateLimitError
from typing import List, Dict, Any, Tuple

##############################################################################
# Configuration: Set your OpenAI API credentials and model information here
##############################################################################

import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Get API key from environment variable
MODEL_ENDPOINT = "https://api.openai.com/v1"  # Default endpoint

# Latest GPT-4 models as of 2025
MODEL_ID = "gpt-4.1-2025-04-14"  # Latest April 2025 release
# Other available models:
# MODEL_ID = "gpt-4-turbo"  # Turbo model
# MODEL_ID = "gpt-4-1106-preview"  # Preview model from November 2023
# MODEL_ID = "gpt-4-vision-preview"  # Vision-enabled model
# MODEL_ID = "gpt-4"  # Base model

# Initialize the OpenAI client with proper timeout settings
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=MODEL_ENDPOINT,
    timeout=60.0,  # Overall timeout in seconds
)

# If using a custom endpoint, configure it like:
# client = OpenAI(
#     api_key=OPENAI_API_KEY, 
#     base_url="https://YOUR_CUSTOM_ENDPOINT/v1",
#     timeout=60.0
# )
##############################################################################
# Agent Prompts
##############################################################################

def get_supervisor_agent_prompt():
    """
    The Supervisor Agent's primary responsibility is to read the scientist's
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
        "agent, and store or update the system's memory as needed. "
        "Ensure that all idea hypotheses include relevant citations where applicable, "
        "using the format [Author Year] for inline citations."
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
        "and scientific rigor. "
        "Where possible, include relevant citations using the format [Author Year] "
        "to support your hypotheses and problem descriptions. If citing specific "
        "literature, include brief source details relevant to understanding the "
        "citation's context. These citations should be maintained throughout the "
        "refinement process."
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
        "so that subsequent agents can refine the ideas further. "
        "Pay attention to the citations included in each hypothesis and assess their "
        "relevance and appropriateness. Suggest additional citations where helpful, "
        "using the format [Author Year]. Maintain all existing citations when providing "
        "feedback."
    )
def get_ranking_agent_prompt():
    """
    The Ranking Agent compares and ranks competing hypotheses or proposals,
    considering multiple criteria including plausibility, novelty, correctness
    likelihood, and additional factors for comprehensive evaluation.
    """
    return (
        "You are the Ranking Agent in a multi-agent AI co-scientist system. "
        "You receive multiple research ideas or proposals, each containing an explicit "
        "hypothesis. Compare and rank them based on eight key criteria: "
        "(1) Hypothesis plausibility, (2) Novelty, (3) Likelihood of correctness, "
        "(4) Methodological rigor - the strength and validity of proposed methods, "
        "(5) Resource efficiency - feasibility with available resources, "
        "(6) Potential impact - possible influence on the field, "
        "(7) Interdisciplinary potential - ability to bridge multiple fields, "
        "(8) Scalability - potential for expansion or broader application. "
        "Evaluate quality and relevance of citations [Author Year]. Produce a "
        "final ranking with rationale for placement."
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
        "more innovative, or more feasible. "
        "Preserve all existing citations in the format [Author Year] and add new "
        "citations where appropriate. If an idea lacks citations, consider adding "
        "relevant ones to strengthen the hypothesis. Never remove existing citations "
        "unless they become irrelevant due to substantial changes in the hypothesis."
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
        "misalignment is detected, provide warnings and corrective suggestions. "
        "Verify that citations are relevant to the research domain and suggest "
        "additional or alternative citations where appropriate, using the format "
        "[Author Year]. Maintain all existing citations in your feedback."
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
        "next steps. Provide a concise but comprehensive overview. "
        "For each of the top 5 ideas, maintain all citations in the format [Author Year] "
        "and if any idea would benefit from additional citations, suggest them where appropriate. "
        "Include a brief 'References' section at the end listing the key citations in alphabetical order."
    )

def get_tournament_agent_prompt():
    """
    The Tournament Agent compares pairs of ideas across multiple criteria and
    provides vector-based scoring for tournament matchups.
    """
    return (
        "You are the Tournament Agent in a multi-agent AI co-scientist system. "
        "For each pair of ideas, you must evaluate them across eight distinct criteria and "
        "provide numerical scores in EXACTLY this format:\n\n"
        "Criterion 1 (Plausibility): Idea A = X, Idea B = Y\n"
        "Criterion 2 (Novelty): Idea A = X, Idea B = Y\n"
        "Criterion 3 (Correctness): Idea A = X, Idea B = Y\n"
        "Criterion 4 (Methodological Rigor): Idea A = X, Idea B = Y\n"
        "Criterion 5 (Resource Efficiency): Idea A = X, Idea B = Y\n"
        "Criterion 6 (Potential Impact): Idea A = X, Idea B = Y\n"
        "Criterion 7 (Interdisciplinary Potential): Idea A = X, Idea B = Y\n"
        "Criterion 8 (Scalability): Idea A = X, Idea B = Y\n\n"
        "Where X and Y are scores between 1-10, where:\n"
        "1-2: Poor performance\n"
        "3-4: Below average\n"
        "5-6: Average\n"
        "7-8: Above average\n"
        "9-10: Exceptional\n\n"
        "IMPORTANT: You MUST maintain this EXACT format for the scores, including the criterion numbers and labels.\n"
        "After providing the scores in this format, you may then provide a brief rationale for each scoring decision."
    )
##############################################################################
##############################################################################
# Helper function to call an agent via the OpenAI ChatCompletion API
##############################################################################

def call_agent(
    agent_system_prompt: str,
    user_prompt: str,
    additional_context: str = "",
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> str:
    """
    Given an agent-specific system prompt, a user-level prompt, and optional
    additional context (e.g., lists of ideas, feedback from other agents), call
    the OpenAI API to get the agent's response.
    
    Includes retry logic with exponential backoff for handling temporary errors.
    """
    messages = [
        {"role": "system", "content": agent_system_prompt},
    ]

    if additional_context:
        messages.append({"role": "assistant", "content": additional_context})

    messages.append({"role": "user", "content": user_prompt})
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
                temperature=0.7,
                timeout=60.0
            )
            return response.choices[0].message.content
            
        except (APITimeoutError, APIConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                print(f"Connection error or timeout. Retrying in {wait_time:.1f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts: {e}")
                raise
                
        except RateLimitError as e:
            wait_time = retry_delay * (2 ** attempt) + 1  # Add extra time for rate limits
            print(f"Rate limit exceeded. Waiting {wait_time:.1f} seconds before retry...")
            time.sleep(wait_time)
            if attempt == max_retries - 1:
                print(f"Failed after {max_retries} attempts: {e}")
                raise
                
        except APIError as e:
            # Don't retry on 4xx errors, only retry on 5xx errors
            if e.status_code and 400 <= e.status_code < 500:
                print(f"Client error {e.status_code}: {e}")
                raise
            
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                print(f"API error {e.status_code}. Retrying in {wait_time:.1f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts: {e}")
                raise
                
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise

##############################################################################
# Main multi-round workflow function
##############################################################################

def run_co_scientist_workflow(
    research_goal: str,
    num_ideas: int = 20,
    num_rounds: int = 4
) -> None:
    """
    Modified workflow that keeps all ideas for four rounds, then runs a tournament:
      1) The Supervisor Agent sets up the initial tasks
      2) Each round:
         - Generation (or Evolution in subsequent rounds) Agent produces/refines ideas
         - Reflection Agent reviews and evaluates hypotheses
         - Proximity Check Agent ensures alignment/feasibility
         - Ranking Agent provides interim rankings
      3) After four rounds, run a tournament where each idea faces 10 random opponents
      4) Calculate final ELO ratings and present ideas in order of rating
      5) After the tournament, the Meta-review Agent generates a final overview
         of the top 5 ideas by ELO rating
    """
    supervisor_intro = call_agent(
        get_supervisor_agent_prompt(),
        user_prompt=(
            f"The user has the research goal: '{research_goal}'. "
            "We will conduct four rounds of idea generation and refinement, "
            "keeping all ideas throughout the process. Each idea will maintain "
            "an explicit hypothesis with relevant citations using the format "
            "[Author Year]. After the rounds, we'll conduct a tournament to "
            "determine the final rankings using eight criteria, including "
            "plausibility, novelty, correctness, methodological rigor, resource efficiency, "
            "potential impact, interdisciplinary potential, and scalability."
        )
    )
    print(supervisor_intro)
    print("")
    # Keep track of all ideas across rounds
    ideas: List[str] = []
    # No longer need to track excluded ideas since we're keeping everything
    # excluded_ideas: List[str] = []

    for round_idx in range(num_rounds):
        print(f"\n========== ROUND {round_idx+1} / {num_rounds} ==========\n")

        # 1) Generate or Evolve Ideas
        if round_idx == 0:
            # First round, generate new ideas
            gen_prompt = (
                f"Please generate {num_ideas} distinct research ideas or hypotheses "
                f"for the goal: '{research_goal}'. For each idea, include an explicit "
                f"hypothesis with relevant citations using the format [Author Year]. "
                f"Include citations to support the hypothesis statement and problem "
                f"description where possible."
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
            # In subsequent rounds, we evolve all existing ideas

            # Evolve existing ideas
            print("=== EVOLUTION AGENT OUTPUT (Refining Existing Ideas) ===")
            ideas_text = "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(ideas)])
            evolve_prompt = (
                f"We have the following {len(ideas)} ideas:\n\n"
                f"{ideas_text}\n\n"
                "Please refine or evolve each idea to be stronger, more novel, or more feasible. "
                "Each must retain an explicit hypothesis along with its citations in [Author Year] format. "
                "Preserve all existing citations and add new ones where appropriate to strengthen "
                "the hypotheses."
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
            f"Please analyze these {len(ideas)} ideas, each with its hypothesis and citations, "
            "for plausibility, novelty, potential flaws, and likelihood of being correct. "
            "Also evaluate the quality and relevance of citations, suggesting additional ones "
            "where appropriate using [Author Year] format:\n\n"
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
            "suggest modifications or indicate if they should be dropped. Also verify that "
            "all citations are relevant and appropriate. Suggest additional citations where helpful:\n\n" 
            + ideas_text
        )
        proximity_output = call_agent(
            get_proximity_check_agent_prompt(),
            user_prompt=proximity_prompt
        )
        print("=== PROXIMITY CHECK AGENT OUTPUT ===")
        print(proximity_output)
        print("")

        # 4) Interim Ranking (for feedback purposes only)
        ranking_prompt = (
            f"We have these {len(ideas)} ideas:\n\n{ideas_text}\n\n"
            "Please provide an interim ranking considering all eight criteria: "
            "(1) Hypothesis plausibility, (2) Novelty, (3) Likelihood of correctness, "
            "(4) Methodological rigor, (5) Resource efficiency, (6) Potential impact, "
            "(7) Interdisciplinary potential, and (8) Scalability. "
            "This is for feedback only - all ideas will continue to the next round."
        )
        ranking_output = call_agent(
            get_ranking_agent_prompt(),
            user_prompt=ranking_prompt
        )
        print("=== RANKING AGENT OUTPUT ===")
        print(ranking_output)
        print("")

        # For the first 3 rounds, we'll reorder ideas for better visibility
        # but we won't remove any
        if round_idx < num_rounds - 1:
            ideas_ordered = parse_ideas_order_from_ranking(ranking_output, ideas)
            ideas = ideas_ordered

        # Supervisor summary of the round
        # Supervisor summary of the round
        round_summary = call_agent(
            get_supervisor_agent_prompt(),
            user_prompt=(
                f"Summarize the results of round {round_idx+1}, referencing the Reflection, "
                f"Proximity Check, and interim Ranking. All ideas will continue "
                f"to the next phase."
            )
        )
        print(round_summary)

    # After all rounds, run the tournament phase
    print("\n========== TOURNAMENT PHASE ==========\n")
    print("Each idea will be compared against 10 random opponents across all criteria.")
    
    # Import functions for tournament
    import random
    from typing import Tuple, NamedTuple
    
    class IdeaScore(NamedTuple):
        plausibility: float
        novelty: float
        correctness: float
        methodological_rigor: float
        resource_efficiency: float
        potential_impact: float
        interdisciplinary_potential: float
        scalability: float
    
    def calculate_vector_score(scores_a: IdeaScore, scores_b: IdeaScore) -> float:
        """
        Calculate a normalized score between two ideas based on their vector scores.
        Returns a value between 0 and 1 representing idea_a's performance vs idea_b.
        """
        # Convert scores to vectors
        vec_a = list(scores_a)
        vec_b = list(scores_b)
        
        # Calculate vector magnitudes
        mag_a = sum(x*x for x in vec_a) ** 0.5
        mag_b = sum(x*x for x in vec_b) ** 0.5
        
        # Normalize to prevent division by zero
        total_mag = mag_a + mag_b
        if total_mag == 0:
            return 0.5  # If both vectors are zero, return draw
        
        # Return normalized score between 0 and 1
        return mag_a / total_mag
    
    def initialize_elo_ratings(ideas: List[str]) -> Dict[str, float]:
        """Initialize each idea with a base ELO rating of 1500."""
        return {idea: 1500.0 for idea in ideas}

    def calculate_elo_update(rating_a: float, rating_b: float, score: float, k: float = 32.0) -> Tuple[float, float]:
        """
        Calculate updated ELO ratings based on the comparison score.
        score should be between 0 and 1, representing idea_a's performance against idea_b.
        """
        expected_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
        update = k * (score - expected_a)
        return rating_a + update, rating_b - update
    def parse_tournament_scores(result: str) -> Tuple[IdeaScore, IdeaScore]:
        """Parse the tournament agent's response to extract scores for both ideas."""
        import re
        
        # Initialize score lists
        scores_a = []
        scores_b = []
        
        # Look for score patterns like "Criterion N (...): Idea A = X, Idea B = Y"
        score_pattern = r'(?i)criterion\s*\d+.*?(?::|[-=]).*?(?:idea\s*a|a)\s*[-=]\s*(\d+)[,\s]+(?:idea\s*b|b)\s*[-=]\s*(\d+)'
        
        # Find all score pairs in the text
        matches = re.finditer(score_pattern, result)
        
        for match in matches:
            score_a = float(match.group(1))
            score_b = float(match.group(2))
            # Validate scores are in range 1-10
            if 1 <= score_a <= 10 and 1 <= score_b <= 10:
                scores_a.append(score_a)
                scores_b.append(score_b)
        
        # If we didn't find exactly 8 scores (our criteria count), something went wrong
        if len(scores_a) != 8 or len(scores_b) != 8:
            print("WARNING: Failed to parse scores from response:")
            print(result)
            raise ValueError("Could not parse exactly 8 scores for each idea")
        
        return (
            IdeaScore(*scores_a),
            IdeaScore(*scores_b)
        )

    def parse_ideas_from_tournament_text(text: str) -> List[str]:
        """Extract individual hypotheses from the tournament text."""
        ideas = []
        # Look for hypothesis sections marked with "**Hypothesis:**"
        hypothesis_pattern = r'\*\*Hypothesis:\*\*\s*([^[]*?)\['
        matches = re.finditer(hypothesis_pattern, text)
        for match in matches:
            hypothesis = match.group(1).strip()
            if hypothesis:
                ideas.append(hypothesis)
        return ideas
    
    def run_tournament(ideas: List[str], tournament_agent_prompt: str) -> List[Tuple[str, float]]:
        """
        Run a tournament where each idea is compared against 10 random other ideas.
        Returns list of (idea, final_elo_rating) tuples sorted by rating.
        Outputs detailed results for each matchup.
        """
        # Extract hypotheses if needed
        if len(ideas) == 1 and '**Hypothesis:**' in ideas[0]:
            ideas = parse_ideas_from_tournament_text(ideas[0])
            if len(ideas) < 2:
                print("ERROR: Could not extract multiple hypotheses from the text.")
                return [(ideas[0], 1500.0)]
        
        # Initialize ELO ratings
        elo_ratings = initialize_elo_ratings(ideas)
        
        print("\n=== TOURNAMENT MATCHUP RESULTS ===")
        
        # For each idea, select 10 random unique opponents
        for i, idea_a in enumerate(ideas):
            print(f"\nIdea {i+1}/{len(ideas)}: Tournament Matchups")
            print("-" * 80)
            
            # Get all possible opponents (excluding self)
            possible_opponents = ideas[:i] + ideas[i+1:]
            # Select 10 random opponents or all if less than 10 available
            num_opponents = min(10, len(possible_opponents))
            opponents = random.sample(possible_opponents, num_opponents)
            
            for match_num, idea_b in enumerate(opponents, 1):
                print(f"\nMatch {match_num}/{num_opponents}:")
                print(f"Idea A (ELO {elo_ratings[idea_a]:.1f}):")
                print(textwrap.fill(idea_a, width=80, initial_indent="  ", subsequent_indent="  "))
                print(f"\nIdea B (ELO {elo_ratings[idea_b]:.1f}):")
                print(textwrap.fill(idea_b, width=80, initial_indent="  ", subsequent_indent="  "))
                
                # Prepare the comparison prompt
                comparison_prompt = (
                    f"Compare these two research ideas across all eight criteria "
                    f"(score each 1-10):\n\nIdea A: {idea_a}\n\nIdea B: {idea_b}\n\n"
                    f"For each criterion, provide a score and brief rationale. "
                    f"Use [Author Year] citations where relevant."
                )
                
                # Get the tournament agent's evaluation
                result = call_agent(
                    tournament_agent_prompt,
                    user_prompt=comparison_prompt
                )
                
                # Parse the scores from the result
                scores_a, scores_b = parse_tournament_scores(result)
                
                # Print detailed scores
                print("\nScores by Criterion:")
                criteria = [
                    "Plausibility", "Novelty", "Correctness", "Methodological Rigor",
                    "Resource Efficiency", "Potential Impact", "Interdisciplinary Potential",
                    "Scalability"
                ]
                for criterion, score_a, score_b in zip(criteria, list(scores_a), list(scores_b)):
                    print(f"  {criterion:25} A: {score_a:4.1f}  B: {score_b:4.1f}")
                
                # Calculate and show vector-based score
                vector_score = calculate_vector_score(scores_a, scores_b)
                print(f"\nVector-based comparison score: {vector_score:.3f}")
                
                # Update and show ELO ratings
                old_rating_a = elo_ratings[idea_a]
                old_rating_b = elo_ratings[idea_b]
                new_rating_a, new_rating_b = calculate_elo_update(
                    old_rating_a,
                    old_rating_b,
                    vector_score
                )
                elo_ratings[idea_a] = new_rating_a
                elo_ratings[idea_b] = new_rating_b
                
                print("\nELO Rating Changes:")
                print(f"  Idea A: {old_rating_a:.1f} → {new_rating_a:.1f} ({new_rating_a - old_rating_a:+.1f})")
                print(f"  Idea B: {old_rating_b:.1f} → {new_rating_b:.1f} ({new_rating_b - old_rating_b:+.1f})")
                print("-" * 80)
        
        # Sort ideas by final ELO rating
        return sorted(
            [(idea, rating) for idea, rating in elo_ratings.items()],
            key=lambda x: x[1],
            reverse=True
        )
    
    # Run the tournament
    tournament_results = run_tournament(ideas, get_tournament_agent_prompt())
    
    # Output final rankings
    # Output final rankings with detailed scores
    print("\n=== FINAL ELO RANKINGS ===")
    print("-" * 80)
    for i, (idea, rating) in enumerate(tournament_results, 1):
        print(f"\n{i}. Final ELO Rating: {rating:.1f}")
        print("Hypothesis:")
        print(textwrap.fill(idea, width=80, initial_indent="  ", subsequent_indent="  "))
    print("-" * 80)
    # Final meta-review of top ideas
    top_5_ideas = [idea for idea, _ in tournament_results[:5]]
    final_ideas_text = "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(top_5_ideas)])
    meta_prompt = (
        f"Here are the final top 5 ideas based on tournament results:\n\n"
        f"{final_ideas_text}\n\n"
        "Please provide a meta-review, summarizing these ideas, their strengths "
        "and weaknesses, and suggest next steps for the scientist."
    )
    meta_review_output = call_agent(
        get_meta_review_agent_prompt(),
        user_prompt=meta_prompt
    )
    print("\n=== META-REVIEW AGENT OUTPUT (TOP 5 BY ELO) ===")
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
        print("Usage: python scientia_gpt41_v2.py <research_goal> [num_ideas]")
        print("  num_ideas: Optional number of ideas to generate (default: 20)")
        sys.exit(1)

    user_research_goal = ' '.join(sys.argv[1:-1]) if len(sys.argv) > 2 and sys.argv[-1].isdigit() else ' '.join(sys.argv[1:])
    num_ideas = int(sys.argv[-1]) if len(sys.argv) > 2 and sys.argv[-1].isdigit() else 20

    print(f"Generating {num_ideas} ideas for research goal: {user_research_goal}")
    run_co_scientist_workflow(
        research_goal=user_research_goal,
        num_ideas=num_ideas,   # Use command-line specified number of ideas
        num_rounds=4    # Default number of iterative rounds
    )
