"""
Scientia: AI-driven scientific idea generation and evaluation system.

This is the main entry point for the Scientia system. It orchestrates the
workflow for generating, evaluating, and refining scientific ideas.

Example usage:
1. Specify research goal directly:
   python main.py --goal How can quantum computing improve machine learning?

2. Load research goal from a file:
   python main.py --goal-file research_questions.txt

3. Customize parameters:
   python main.py --goal-file research_questions.txt -i 30 -f 10 --debug

4. Specify models:
   python main.py --goal "Develop novel quantum algorithms" -m gpt4o -r claude3
"""

import sys
import os
import time
import traceback
import argparse
import textwrap
import random
from typing import List, Dict, Any, Tuple, Optional, Set

from openai import OpenAI

# Import from core modules
from core.models import IdeaEvolution, TOURNAMENT_CRITERIA
from core.agents import (
    call_agent, initialize_client, load_model_configs,
    get_generation_agent_prompt, get_ranking_agent_prompt, 
    get_evolution_agent_prompt, get_proximity_check_agent_prompt,
    get_reflection_agent_prompt, get_tournament_agent_prompt, 
    get_meta_review_agent_prompt, get_supervisor_agent_prompt,
    DEBUG_MODE
)
from core.tournament import run_optimized_tournament
from core.file_utils import (
    generate_problem_name, create_scientia_directory, log_idea, save_checkpoint,
    extract_idea_specific_feedback, write_file
)
from core.idea_parser import (
    parse_structured_idea, is_significant_change,
    parse_ideas_from_text, parse_ideas_order_from_ranking,
    extract_citations
)
from core.evaluation import evaluate_idea_with_criteria, generate_final_report

# Client instances for different models (will be set after parsing arguments)
main_client = None
reflection_client = None
MAIN_MODEL_ID = None
REFLECTION_MODEL_ID = None
MODEL_CONFIG = None
MODEL_ID = None
client = None

# Global variable to store idea score vectors for reuse
idea_score_vectors = {}


def run_co_scientist_workflow(
    research_goal: str,
    num_initial_ideas: int = 20,
    num_rounds: int = 4,
    max_new_ideas_per_round: int = 2,  # Maximum new ideas to generate each round
    min_ideas: int = 15,  # Minimum ideas to maintain
    max_ideas: int = 30,  # Maximum total ideas allowed
    num_final_ideas: int = 5,  # Number of ideas to include in final report
    output_dir: Optional[str] = None  # Directory for output files and logs
) -> None:
    """
    Enhanced workflow that supports idea evolution and dynamic idea sets:
    1. Generate initial ideas or evolve existing ones
    2. Run reflection, proximity check, and (in later rounds) ranking for each round
    3. After four rounds, run a tournament with precomputed scores
    4. Calculate final ELO ratings and present ideas in order of rating
    5. Meta-review Agent generates final overview of top ideas
    6. Generate comprehensive final reports in the scientia directory
    
    Args:
        research_goal: The research question or goal to explore
        num_initial_ideas: Number of ideas to generate in first round
        num_rounds: Number of evolution rounds to run
        max_new_ideas_per_round: Maximum new ideas to generate per round
        min_ideas: Minimum number of ideas to maintain
        max_ideas: Maximum total ideas allowed
        num_final_ideas: Number of ideas to include in final report
        output_dir: Directory for output files and logs
    """
    # Generate a short problem name and create a directory for this run
    scientia_dir = None
    try:
        problem_name = generate_problem_name(research_goal)
        if output_dir:
            # Use specified output directory
            scientia_dir = os.path.join(output_dir, f"{problem_name}.scientia")
            if not os.path.exists(scientia_dir):
                os.makedirs(scientia_dir)
            print(f"Created directory: {scientia_dir} for tracking idea evolution\n")
        else:
            # Use auto-generated directory
            scientia_dir = create_scientia_directory(problem_name)
            print(f"Created directory: {scientia_dir} for tracking idea evolution\n")
    except Exception as e:
        print(f"Warning: Failed to create directory: {e}")
    
    user_prompt = (
        f"The user has provided the research goal: '{research_goal}'. "
        f"Your task is to provide a comprehensive introduction to the multi-round research idea generation process.\n\n"
        f"First, explain the research goal in your own words to demonstrate understanding.\n\n"
        f"Then, outline the process we'll follow:\n"
        f"1. We will conduct {num_rounds} rounds of idea generation and refinement\n"
        f"2. Each round will include reflection, proximity checking, and (in later rounds) ranking\n"
        f"3. Ideas will be both refined and new ones will be generated\n"
        f"4. Each idea will maintain an explicit hypothesis with relevant citations using [Author Year] format\n"
        f"5. After all rounds, we'll conduct a tournament to determine final rankings\n\n"
        f"Keep your introduction focused specifically on this research goal and provide a clear roadmap "
        f"for the agents involved in each phase of the process."
    )
    
    print("DEBUG: entering supervisor agent call")
    supervisor_intro = call_agent(
        get_supervisor_agent_prompt(),
        user_prompt=user_prompt,
        agent_name="supervisor"
    )
    print("DEBUG: supervisor agent call returned")
    print(supervisor_intro)
    print("")
    
    # Initialize idea evolution tracker
    idea_tracker = IdeaEvolution()
    
    # Track current round's ideas for tournament
    current_ideas: Dict[int, str] = {}
    ideas: List[str] = []
    
    for round_idx in range(num_rounds):
        print(f"\n========== ROUND {round_idx+1} / {num_rounds} ==========\n")

        # 1) Generate or Evolve Ideas
        if round_idx == 0:
            # First round, generate initial ideas
            gen_prompt = (
                f"Please generate {num_initial_ideas} distinct research ideas or hypotheses "
                f"for the goal: '{research_goal}'. For each idea, include an explicit "
                f"hypothesis with relevant citations using the format [Author Year]. "
                f"Include citations to support the hypothesis statement and problem "
                f"description where possible."
            )
            print("DEBUG: entering generation agent call")
            generation_output = call_agent(
                get_generation_agent_prompt(),
                user_prompt=gen_prompt,
                agent_name="generation"
            )
            print("DEBUG: generation agent call returned")
            initial_ideas = parse_ideas_from_text(generation_output, expected_count=num_initial_ideas)
            
            # Add initial ideas to tracker with expanded evaluations
            idea_evaluations = {}  # Store evaluations for each idea
            
            for i, idea_text in enumerate(initial_ideas):
                print(f"\nProcessing initial idea {i+1}/{len(initial_ideas)}...")
                
                # Generate a unique ID for this idea
                idea_id = idea_tracker.add_initial_idea(idea_text)
                current_ideas[idea_id] = idea_text
                
                # Get the metadata for this idea
                idea_metadata = idea_tracker.get_metadata(idea_id)
                unique_id = idea_metadata.unique_id
                
                print(f"Evaluating idea {idea_id} against scientific criteria...")
                # Evaluate idea against scientific criteria
                criteria_scores, evaluation_text = evaluate_idea_with_criteria(
                    idea_text, 
                    research_goal, 
                    get_tournament_agent_prompt()
                )
                
                # Update metadata with criteria scores
                idea_tracker.update_criteria_scores(idea_id, criteria_scores)
                
                # Store the evaluation for logging
                idea_evaluations[idea_id] = {
                    "idea_text": idea_text,
                    "unique_id": unique_id,
                    "criteria_scores": criteria_scores,
                    "evaluation_text": evaluation_text,
                    "metadata": idea_metadata
                }
                
                print(f"Idea {idea_id} processed and evaluated.")
            
            # Convert current_ideas to list for compatibility
            ideas = list(current_ideas.values())
            
            # Log each newly generated idea with its evaluation
            if scientia_dir:
                try:
                    for idea_id, eval_data in idea_evaluations.items():
                        # Format the evaluation as markdown for the idea-specific file
                        formatted_evaluation = f"## Initial Idea\n\n{eval_data['idea_text']}\n\n"
                        formatted_evaluation += f"## Scientific Evaluation\n\n"
                        
                        # Add criteria scores in a formatted table
                        formatted_evaluation += "| Criterion | Score |\n|---|---:|\n"
                        for criterion, score in eval_data["criteria_scores"].items():
                            formatted_evaluation += f"| {criterion} | {score:.1f}/10 |\n"
                        
                        formatted_evaluation += f"\n## Detailed Evaluation\n\n{eval_data['evaluation_text']}\n\n"
                        
                        # Log to idea-specific file with metadata
                        log_idea(
                            scientia_dir,
                            idea_id,
                            formatted_evaluation,
                            "Initial Generation",
                            round_idx+1,
                            unique_id=eval_data["unique_id"],
                            metadata=eval_data["metadata"]
                        )
                except Exception as e:
                    print(f"Warning: Failed to log ideas: {e}")
                    import traceback
                    traceback.print_exc()
            
            print("=== GENERATION AGENT OUTPUT ===")
            print(generation_output)
            print("")
        else:
            # In subsequent rounds, we evolve existing ideas and potentially generate new ones
            print("=== EVOLUTION AGENT OUTPUT ===")
            
            # Prepare existing ideas text with their IDs and include reflection feedback
            ideas_text = ""
            for idea_id, idea_text in current_ideas.items():
                ideas_text += f"Idea {idea_id}:\n{idea_text}\n\n"
                
                # Add reflection feedback for this idea if available
                idea_specific_feedback = extract_idea_specific_feedback(reflection_output, idea_id, len(current_ideas), idea_text)
                if idea_specific_feedback:
                    ideas_text += f"REFLECTION FEEDBACK FOR IDEA {idea_id}:\n{idea_specific_feedback}\n\n"
                
                ideas_text += "---\n\n"  # Separator between ideas
            
            # Calculate how many new ideas we can add, respecting command line parameter
            current_count = len(current_ideas)
            space_for_new = min(
                max_new_ideas_per_round,
                max_ideas - current_count
            )
            
            evolve_prompt = (
                f"We have the following {current_count} ideas with their reflection feedback:\n\n"
                f"{ideas_text}\n\n"
                f"1. Please refine and strengthen each existing idea using the provided strategies and addressing the reflection feedback.\n"
                f"2. If the reflection feedback suggests a SIGNIFICANT change to an idea's core premise or approach, create it as a new idea rather than a refinement.\n"
                f"3. After refining existing ideas and creating significant-change new ideas, "
            )
            
            if space_for_new > 0:
                evolve_prompt += (
                    f"generate up to {space_for_new} NEW complementary ideas that explore "
                    f"novel angles not covered by the existing ideas."
                )
            else:
                evolve_prompt += (
                    "focus solely on refining existing ideas as we've reached the "
                    "maximum allowed idea count."
                )
            
            # Get the evolution output from the agent
            evolution_output = call_agent(
                get_evolution_agent_prompt(),
                user_prompt=evolve_prompt,
                agent_name="evolution"
            )
            
            # Parse evolved ideas and potential new ideas
            print("Parsing evolution output...")  # Add debug message
            all_evolved_ideas = parse_ideas_from_text(
                evolution_output,
                expected_count=current_count + space_for_new
            )
            
            # Split into refined and new ideas
            refined_ideas = all_evolved_ideas[:current_count]
            new_ideas = all_evolved_ideas[current_count:]
            
            # Process refined ideas
            orig_ids = list(idea_tracker.get_all_ideas().keys())
            for idx, refined_text in enumerate(refined_ideas):
                if idx < len(orig_ids):
                    original_id = orig_ids[idx]
                    original_idea = idea_tracker.ideas.get(original_id, "")
                    
                    # Check if this is a significant change
                    is_significant = is_significant_change(original_idea, refined_text)
                    
                    if is_significant:
                        # This is a significant change, so add it as a new idea with parent reference
                        print(f"\nDetected significant change for idea {original_id} - creating as new idea")
                        idea_id = idea_tracker.add_new_idea(refined_text)
                        # Set parent reference manually
                        idea_tracker.metadata[idea_id].parent_id = original_id
                        original_metadata = idea_tracker.get_metadata(original_id)
                        if hasattr(original_metadata, 'unique_id'):
                            idea_tracker.metadata[idea_id].parent_unique_id = original_metadata.unique_id
                        current_ideas[idea_id] = refined_text
                        generation_type = "New (Significant Change)"
                    else:
                        # Regular refinement
                        idea_id = idea_tracker.add_refined_idea(original_id, refined_text)
                        current_ideas[idea_id] = refined_text
                        generation_type = "Refinement"
                    
                    # Get metadata for original and refined ideas
                    original_metadata = idea_tracker.get_metadata(original_id)
                    metadata = idea_tracker.get_metadata(idea_id)
                    
                    # Evaluate refined idea against scientific criteria
                    print(f"\nEvaluating idea {idea_id} ({generation_type}) against scientific criteria...")
                    criteria_scores, evaluation_text = evaluate_idea_with_criteria(
                        refined_text,
                        research_goal,
                        get_tournament_agent_prompt()
                    )
                    
                    # Update metadata with criteria scores
                    idea_tracker.update_criteria_scores(idea_id, criteria_scores)
                    
                    if scientia_dir:
                        try:
                            # Original idea for comparison
                            original_idea = idea_tracker.ideas.get(original_id, "Original idea not found")
                            
                            # Format the evaluation as markdown
                            if is_significant:
                                formatted_evaluation = f"## New Idea from Significant Change (Round {round_idx+1})\n\n"
                                formatted_evaluation += f"This idea represents a significant change from Idea {original_id}.\n\n"
                            else:
                                formatted_evaluation = f"## Refined Idea (Round {round_idx+1})\n\n"
                            
                            formatted_evaluation += f"{refined_text}\n\n"
                            
                            # Show comparison with original
                            formatted_evaluation += f"## Comparison with Original\n\n"
                            formatted_evaluation += f"### Original Idea (ID: {original_id})\n\n{original_idea}\n\n"
                            
                            # Add criteria scores in a formatted table
                            formatted_evaluation += "### Scientific Evaluation\n\n"
                            formatted_evaluation += "| Criterion | Score |\n|---|---:|\n"
                            for criterion, score in criteria_scores.items():
                                formatted_evaluation += f"| {criterion} | {score:.1f}/10 |\n"
                            
                            formatted_evaluation += f"\n### Detailed Evaluation\n\n{evaluation_text}\n\n"
                            
                            # Add metadata information
                            formatted_evaluation += f"### Metadata\n\n"
                            formatted_evaluation += f"- Generation Type: {generation_type}\n"
                            formatted_evaluation += f"- Parent Idea: {metadata.parent_id}\n"
                            
                            if is_significant:
                                formatted_evaluation += "- Created as new idea due to significant change\n"
                            else:
                                formatted_evaluation += f"- Refinement Count: {metadata.refinement_count}\n"
                            
                            # Log with unique ID
                            log_idea(
                                scientia_dir,
                                idea_id,
                                formatted_evaluation,
                                "Evolution" if not is_significant else "New Idea (Significant Change)",
                                round_idx+1,
                                unique_id=metadata.unique_id,
                                metadata=metadata
                            )
                        except Exception as e:
                            print(f"Warning: Failed to log idea: {e}")
                            traceback.print_exc()
            
            # Process new ideas (if any)
            for new_idea_text in new_ideas:
                idea_id = idea_tracker.add_new_idea(new_idea_text)
                current_ideas[idea_id] = new_idea_text
                
                # Get metadata for the new idea
                metadata = idea_tracker.get_metadata(idea_id)
                
                # Evaluate new idea against scientific criteria
                print(f"\nEvaluating new idea {idea_id} against scientific criteria...")
                criteria_scores, evaluation_text = evaluate_idea_with_criteria(
                    new_idea_text,
                    research_goal,
                    get_tournament_agent_prompt()
                )
                
                # Update metadata with criteria scores
                idea_tracker.update_criteria_scores(idea_id, criteria_scores)
                
                if scientia_dir:
                    try:
                        # Format the evaluation as markdown
                        formatted_evaluation = f"## New Idea (Generated in Round {round_idx+1})\n\n{new_idea_text}\n\n"
                        
                        # Add criteria scores in a formatted table
                        formatted_evaluation += "### Scientific Evaluation\n\n"
                        formatted_evaluation += "| Criterion | Score |\n|---|---:|\n"
                        for criterion, score in criteria_scores.items():
                            formatted_evaluation += f"| {criterion} | {score:.1f}/10 |\n"
                        
                        formatted_evaluation += f"\n### Detailed Evaluation\n\n{evaluation_text}\n\n"
                        
                        # Add metadata information
                        formatted_evaluation += f"### Metadata\n\n"
                        formatted_evaluation += f"- Generation Type: {metadata.generation_type}\n"
                        formatted_evaluation += f"- New Idea Generated During Evolution\n"
                        
                        # Log with unique ID
                        log_idea(
                            scientia_dir,
                            idea_id,
                            formatted_evaluation,
                            "New Idea",
                            round_idx+1,
                            unique_id=metadata.unique_id,
                            metadata=metadata
                        )
                    except Exception as e:
                        print(f"Warning: Failed to log new idea: {e}")
                        traceback.print_exc()
            
            print(evolution_output)
            print("")
            
            # Update ideas list for compatibility with the rest of the code
            ideas = list(current_ideas.values())
            
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
            user_prompt=reflection_prompt,
            agent_name="reflection"
        )
        print("=== REFLECTION AGENT OUTPUT ===")
        print(reflection_output)
        print("")
        
        # Log the reflection feedback for each idea
        if scientia_dir:
            try:
                for i, idea in enumerate(ideas):
                    reflection_entry = f"{idea}\n\n--- REFLECTION FEEDBACK ---\n\n{reflection_output}"
                    # Find idea's metadata and unique ID
                    idea_metadata = None
                    idea_unique_id = None
                    for id, text in idea_tracker.get_all_ideas().items():
                        if text == idea:
                            idea_metadata = idea_tracker.get_metadata(id)
                            idea_unique_id = idea_metadata.unique_id
                            break
                    
                    log_idea(scientia_dir, i+1, reflection_entry, "Reflection", round_idx+1, 
                             unique_id=idea_unique_id, metadata=idea_metadata)
            except Exception as e:
                print(f"Warning: Failed to log reflection: {e}")

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
            user_prompt=proximity_prompt,
            agent_name="proximity"
        )
        print("=== PROXIMITY CHECK AGENT OUTPUT ===")
        print(proximity_output)
        print("")
        
        # Log proximity check results
        if scientia_dir:
            try:
                for i, idea in enumerate(ideas):
                    proximity_entry = f"{idea}\n\n--- PROXIMITY CHECK FEEDBACK ---\n\n{proximity_output}"
                    # Find idea's metadata and unique ID
                    idea_metadata = None
                    idea_unique_id = None
                    for id, text in idea_tracker.get_all_ideas().items():
                        if text == idea:
                            idea_metadata = idea_tracker.get_metadata(id)
                            idea_unique_id = idea_metadata.unique_id
                            break
                    
                    log_idea(scientia_dir, i+1, proximity_entry, "Proximity Check", round_idx+1,
                             unique_id=idea_unique_id, metadata=idea_metadata)
            except Exception as e:
                print(f"Warning: Failed to log proximity check: {e}")

        # 4) Rank ideas (skip in first three rounds to focus on improvement)
        if round_idx >= 3:
            # Create ranking prompt using global TOURNAMENT_CRITERIA
            criteria_list = ", ".join([f"({i+1}) {criterion}" for i, criterion in enumerate(TOURNAMENT_CRITERIA)])
            ranking_prompt = (
                f"Please provide an interim ranking considering these sixteen criteria: "
                f"{criteria_list}. "
                f"This is for feedback only - all ideas will continue to the next round."
            )
            ranking_output = call_agent(
                get_ranking_agent_prompt(),
                user_prompt=ranking_prompt,
                agent_name="ranking"
            )
            print("=== RANKING AGENT OUTPUT ===")
            print(ranking_output)
            print("")
            
            # Log the ranking feedback for each idea
            if scientia_dir:
                try:
                    for i, idea in enumerate(ideas):
                        ranking_entry = f"{idea}\n\n--- RANKING FEEDBACK ---\n\n{ranking_output}"
                        # Find idea's metadata and unique ID
                        idea_metadata = None
                        idea_unique_id = None
                        for id, text in idea_tracker.get_all_ideas().items():
                            if text == idea:
                                idea_metadata = idea_tracker.get_metadata(id)
                                idea_unique_id = idea_metadata.unique_id
                                break
                        
                        log_idea(scientia_dir, i+1, ranking_entry, "Ranking", round_idx+1,
                                 unique_id=idea_unique_id, metadata=idea_metadata)
                except Exception as e:
                    print(f"Warning: Failed to log ranking: {e}")

            # Reorder ideas based on ranking
            ideas_ordered = parse_ideas_order_from_ranking(ranking_output, ideas)
            ideas = ideas_ordered
        else:
            print("=== SKIPPING RANKING FOR THIS ROUND ===")
            print("Focusing on improvement only in the first three rounds.")
            print("")
        
        # Run a mini-tournament for this round and update ELO scores
        print("\n=== RUNNING MINI-TOURNAMENT FOR THIS ROUND ===")
        # Track which ideas were improved in this round
        if round_idx == 0:
            # First round, all ideas are new
            improved_ideas = ideas
        else:
            # In subsequent rounds, identify new and refined ideas based on evolution
            improved_ideas = []
            # Get the original IDs that existed at the start of this round
            orig_ids = list(idea_tracker.get_all_ideas().keys())
            # Add all ideas that were refined in this round (assuming original order is preserved)
            for idx, idea in enumerate(ideas):
                # If index is within original IDs and the text changed, it was improved
                if idx < len(orig_ids) and idea != current_ideas.get(orig_ids[idx], ""):
                    improved_ideas.append(idea)
            # Add any new ideas generated in this round
            current_count = len(current_ideas)
            if len(ideas) > current_count:
                for idx in range(current_count, len(ideas)):
                    improved_ideas.append(ideas[idx])
        
        # Only compute score vectors for improved ideas, saving computation
        if improved_ideas:
            print(f"Computing score vectors for {len(improved_ideas)} improved ideas...")
            mini_tournament_results = run_optimized_tournament(
                ideas, 
                get_tournament_agent_prompt(), 
                num_opponents=min(5, len(ideas)-1),  # Smaller opponent set for mini-tournament
                scientia_dir=scientia_dir,
                only_update_ideas=improved_ideas,  # Only update vectors for improved ideas
                idea_tracker=idea_tracker  # Pass idea_tracker to use stored criteria scores
            )
            
            # Log mini-tournament results
            print(f"Mini-tournament completed. Updated ELO scores for {len(improved_ideas)} ideas based on their criteria scores.")
            
            # Log mini-tournament results for each improved idea
            if scientia_dir:
                try:
                    for i, idea in enumerate(improved_ideas):
                        # Find the idea's ID in current_ideas
                        idea_id = None
                        for id, text in current_ideas.items():
                            if text == idea:
                                idea_id = id
                                break
                        
                        if idea_id is not None:
                            # Get the current ELO rating for this idea
                            elo_rating = None
                            for result_idea, result_rating in mini_tournament_results:
                                if result_idea == idea:
                                    elo_rating = result_rating
                                    break
                            
                            if elo_rating is not None:
                                # Log the mini-tournament result
                                tournament_entry = f"Mini-Tournament (Round {round_idx+1})\nELO Rating: {elo_rating:.1f}\n\n{idea}"
                                # Get metadata for this idea
                                idea_metadata = idea_tracker.get_metadata(idea_id)
                                idea_unique_id = idea_metadata.unique_id
                                
                                log_idea(scientia_dir, idea_id, tournament_entry, "Mini-Tournament", round_idx+1, 
                                         elo_score=elo_rating, unique_id=idea_unique_id, metadata=idea_metadata)
                except Exception as e:
                    print(f"Warning: Failed to log mini-tournament results: {e}")
        else:
            print("No ideas were improved this round. Skipping mini-tournament.")
            
        # Create a comprehensive prompt for the supervisor that includes all the outputs
        supervisor_prompt = (
            f"Summarize the results of round {round_idx+1}. All ideas will continue to the next phase.\n\n"
            f"REFLECTION OUTPUT:\n{reflection_output}\n\n"
            f"PROXIMITY CHECK OUTPUT:\n{proximity_output}\n\n"
        )
        
        # Add ranking output if it was generated in this round
        if round_idx >= 3:
            supervisor_prompt += f"RANKING OUTPUT:\n{ranking_output}\n\n"
        else:
            supervisor_prompt += "Note: Ranking was skipped in this round as it's an early round focusing on idea improvement.\n\n"
            
        round_summary = call_agent(
            get_supervisor_agent_prompt(),
            user_prompt=supervisor_prompt,
            agent_name="supervisor"
        )
        print(round_summary)
        
        # Log the supervisor's summary
        if scientia_dir:
            try:
                for i, idea in enumerate(ideas):
                    summary_entry = f"{idea}\n\n--- SUPERVISOR SUMMARY (ROUND {round_idx+1}) ---\n\n{round_summary}"
                    # Find idea's metadata and unique ID
                    idea_metadata = None
                    idea_unique_id = None
                    for id, text in idea_tracker.get_all_ideas().items():
                        if text == idea:
                            idea_metadata = idea_tracker.get_metadata(id)
                            idea_unique_id = idea_metadata.unique_id
                            break
                    
                    log_idea(scientia_dir, i+1, summary_entry, "Round Summary", round_idx+1,
                             unique_id=idea_unique_id, metadata=idea_metadata)
            except Exception as e:
                print(f"Warning: Failed to log round summary: {e}")
            
    
    # After all rounds, run the tournament phase
    print("\n========== TOURNAMENT PHASE ==========\n")
    print("Running optimized tournament with pre-computed score vectors...")
    tournament_results = run_optimized_tournament(
        ideas, 
        get_tournament_agent_prompt(), 
        scientia_dir=scientia_dir,
        idea_tracker=idea_tracker  # Use stored criteria scores
    )
    
    # Log final tournament results for each idea
    if scientia_dir:
        try:
            print("\nLogging final tournament results...")
            for i, (idea, rating) in enumerate(tournament_results):
                # Find the idea's index in the original list
                original_idx = ideas.index(idea) if idea in ideas else i
                idea_num = original_idx + 1
                
                # Find the idea's metadata by searching through all ideas in the tracker
                idea_metadata = None
                idea_unique_id = None
                for id, text in idea_tracker.get_all_ideas().items():
                    if text == idea:
                        idea_metadata = idea_tracker.get_metadata(id)
                        idea_unique_id = idea_metadata.unique_id
                        break
                
                # Format the entry as markdown
                tournament_entry = f"## Final Tournament Results\n\n"
                tournament_entry += f"**Final ELO Rating:** {rating:.1f}\n\n"
                tournament_entry += f"**Rank:** {i+1} out of {len(ideas)}\n\n"
                
                # Include the ranking context
                tournament_entry += "### Rankings Context\n\n"
                tournament_entry += "| Rank | Idea | ELO Rating |\n|---:|---|---:|\n"
                
                # Include the top 5 ideas and this idea (if not in top 5)
                top_count = min(5, len(tournament_results))
                included_ranks = set()
                
                # Add this idea's rank if not in top 5
                this_rank = i + 1
                if this_rank > top_count:
                    included_ranks.add(this_rank)
                
                # Add top ideas
                for j in range(min(top_count, len(tournament_results))):
                    included_ranks.add(j + 1)
                
                # Sort ranks and create table
                for rank in sorted(included_ranks):
                    j = rank - 1  # Convert rank to index
                    other_idea, other_rating = tournament_results[j]
                    if other_idea == idea:
                        tournament_entry += f"| **{rank}** | **This idea** | **{other_rating:.1f}** |\n"
                    else:
                        other_sections = parse_structured_idea(other_idea)
                        other_title = other_sections.get("title", "Untitled")
                        tournament_entry += f"| {rank} | {other_title[:50]}{'...' if len(other_title) > 50 else ''} | {other_rating:.1f} |\n"
                
                # Add the full idea text for reference
                tournament_entry += f"\n### This Idea\n\n{idea}\n\n"
                
                # Log to idea-specific file with metadata and unique ID
                log_idea(
                    scientia_dir, 
                    idea_num, 
                    tournament_entry, 
                    "Final Tournament Results", 
                    elo_score=rating,
                    unique_id=idea_unique_id,
                    metadata=idea_metadata
                )
        except Exception as e:
            print(f"Warning: Failed to log final tournament results: {e}")
            traceback.print_exc()
    
    # Output final rankings with detailed scores
    print("\n=== FINAL ELO RANKINGS ===")
    print("-" * 80)
    for i, (idea, rating) in enumerate(tournament_results, 1):
        print(f"\n{i}. Final ELO Rating: {rating:.1f}")
        # Extract the title and key idea for display (showing full title)
        sections = parse_structured_idea(idea)
        title = sections.get("title", "")
        key_idea = sections.get("key_idea", "")
        print(f"Title: {title}")
        print("Key Idea:")
        print(textwrap.fill(key_idea or idea[:500], width=80, initial_indent="  ", subsequent_indent="  "))
    print("-" * 80)
    
    # Get the top N ideas for meta-review based on command line argument
    top_ideas = tournament_results[:num_final_ideas]
    final_ideas_text = "\n\n".join([f"{i+1}. {idea}" for i, (idea, _) in enumerate(top_ideas)])
    
    # Create meta-review prompt for final analysis
    meta_prompt = (
        f"Please analyze the top {num_final_ideas} ideas in detail:\n\n{final_ideas_text}\n\n"
        f"For your analysis:\n"
        f"1. Summarize the key hypotheses and their potential impact\n"
        f"2. Analyze the strengths and limitations of each idea, noting potential impact and feasibility\n"
        f"3. Identify cross-cutting themes or complementary approaches across these ideas\n"
        f"4. Suggest practical next steps for validating or implementing each idea\n"
        f"5. Recommend potential collaborations or interdisciplinary connections\n\n"
        f"For each idea, include relevant citations from the existing references, and suggest "
        f"additional key literature in the format [Author Year] that would strengthen the research. "
        f"Your meta-review should synthesize the final, evolved state of each idea, including "
        f"improvements made throughout the iterative process."
    )
    
    # Call the meta-review agent
    meta_review_output = call_agent(
        get_meta_review_agent_prompt(),
        user_prompt=meta_prompt,
        agent_name="meta-review"
    )
    
    print(f"\n=== META-REVIEW AGENT OUTPUT (TOP {num_final_ideas} BY ELO) ===")
    print(meta_review_output)
    
    # Log the meta-review
    if scientia_dir:
        try:
            # Save meta-review to a separate file
            meta_review_file = os.path.join(scientia_dir, "meta_review.md")
            with open(meta_review_file, 'w', encoding='utf-8') as f:
                f.write(f"# Meta-Review of Top {num_final_ideas} Ideas\n\n")
                f.write(f"## Top {num_final_ideas} Ideas by ELO Rating\n\n")
                for i, (idea, rating) in enumerate(tournament_results[:num_final_ideas], 1):
                    f.write(f"### {i}. Idea (ELO: {rating:.1f})\n\n")
                    f.write(f"{idea}\n\n")
                f.write("## Meta-Review Analysis\n\n")
                f.write(meta_review_output)
            
            print(f"\nMeta-review saved to: {meta_review_file}")
            
            # Also log the meta-review for each of the top ideas
            for i, (idea, rating) in enumerate(tournament_results[:num_final_ideas]):
                original_idx = ideas.index(idea) if idea in ideas else i
                idea_num = original_idx + 1
                
                # Find the idea's metadata by searching through all ideas in the tracker
                idea_metadata = None
                idea_unique_id = None
                for id, text in idea_tracker.get_all_ideas().items():
                    if text == idea:
                        idea_metadata = idea_tracker.get_metadata(id)
                        idea_unique_id = idea_metadata.unique_id
                        break
                
                # Format the meta-review as markdown
                meta_entry = f"## Meta-Review of Top Ideas\n\n"
                meta_entry += f"**This idea ranked {i+1} out of {num_final_ideas} top ideas.**\n\n"
                meta_entry += f"**Final ELO Score:** {rating:.1f}\n\n"
                meta_entry += f"### Meta-Review Analysis\n\n{meta_review_output}\n\n"
                
                # Add a table of top ideas
                meta_entry += "### Top Ideas Overview\n\n"
                meta_entry += "| Rank | Idea | ELO Rating |\n|---:|---|---:|\n"
                
                for j, (top_idea, top_rating) in enumerate(tournament_results[:num_final_ideas]):
                    top_sections = parse_structured_idea(top_idea)
                    top_title = top_sections.get("title", "Untitled")
                    
                    if top_idea == idea:
                        meta_entry += f"| **{j+1}** | **This idea** | **{top_rating:.1f}** |\n"
                    else:
                        meta_entry += f"| {j+1} | {top_title[:50]}{'...' if len(top_title) > 50 else ''} | {top_rating:.1f} |\n"
                
                # Log with unique ID and metadata
                log_idea(
                    scientia_dir, 
                    idea_num, 
                    meta_entry, 
                    "Meta-Review", 
                    elo_score=rating,
                    unique_id=idea_unique_id,
                    metadata=idea_metadata
                )
        except Exception as e:
            print(f"Warning: Failed to save meta-review: {e}")
    
    # Generate comprehensive final reports for each idea
    if scientia_dir:
        try:
            print("\nGenerating comprehensive final reports...")
            for i, (idea, rating) in enumerate(tournament_results):
                # Find the idea's index in the original list
                original_idx = ideas.index(idea) if idea in ideas else i
                idea_num = original_idx + 1
                log_file_path = os.path.join(scientia_dir, f"idea_{idea_num}.log")
                if os.path.exists(log_file_path):
                    try:
                        generate_final_report(scientia_dir, idea_num, idea, rating, log_file_path, idea_tracker)
                        print(f"Generated final report for idea {idea_num}")
                    except Exception as e:
                        print(f"Error generating report for idea {idea_num}: {e}")
                        traceback.print_exc()
                else:
                    print(f"Warning: Log file not found for idea {idea_num}")
            
            print(f"\nAll final reports saved to: {scientia_dir}")
            
            # Create a summary file with links to all idea reports
            summary_file = os.path.join(scientia_dir, "summary.md")
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"# Research Summary: {problem_name}\n\n")
                f.write(f"## Research Goal\n\n{research_goal}\n\n")
                f.write("## Ideas Ranked by ELO Rating\n\n")
                
                for i, (idea, rating) in enumerate(tournament_results, 1):
                    original_idx = ideas.index(idea) if idea in ideas else i-1
                    idea_num = original_idx + 1
                    f.write(f"{i}. **[Idea {idea_num}](idea_{idea_num}_final.md)** - ELO: {rating:.1f}\n\n")
                    sections = parse_structured_idea(idea)
                    f.write(f"   **Title**: {sections.get('title', 'Untitled')}\n\n")
                    f.write(f"   **Key Idea**: {sections.get('key_idea', 'No summary available')[:100]}...\n\n")
                
                f.write("\n## Meta-Review\n\n")
                f.write("See the [full meta-review](meta_review.md) for detailed analysis of the top ideas.\n")
            
            print(f"Summary document created: {summary_file}")
        except Exception as e:
            print(f"Warning: Error generating final reports: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scientia: AI-driven scientific idea generation and evaluation")
    
    # Create a mutually exclusive group for research goal specification methods
    research_group = parser.add_mutually_exclusive_group(required=True)
    research_group.add_argument("--goal", nargs="+", dest="research_goal",
                          help="The research question or goal to explore (as command line arguments)")
    research_group.add_argument("--goal-file", dest="goal_file", type=str,
                          help="Path to a file containing the research question or goal")
    
    # Optional arguments
    parser.add_argument("-i", "--initial-ideas", type=int, default=20,
                        help="Number of initial ideas to generate (default: 20)")
    parser.add_argument("-n", "--new-per-round", type=int, default=2,
                        help="Number of new ideas to generate per round (default: 2)")
    parser.add_argument("-f", "--final-ideas", type=int, default=5,
                        help="Number of ideas to include in final report (default: 5)")
    parser.add_argument("--min-ideas", type=int, default=None,
                        help="Minimum ideas to maintain during evolution (default: max(15, initial_ideas-5))")
    parser.add_argument("--max-ideas", type=int, default=None,
                        help="Maximum total ideas allowed, no hard limit (default: max(30, initial_ideas+10))")
    parser.add_argument("--debug", action="store_true", 
                        help="Enable detailed debug logging (default: debug logging disabled)")
    parser.add_argument("-m", "--model", type=str, default="gpt41",
                        help="Main model to use for all agents except reflection (default: gpt41)")
    parser.add_argument("-r", "--reflection-model", type=str,
                        help="Model to use for reflection agent (default: same as main model)")
    parser.add_argument("-o", "--output-dir", type=str, default=None,
                        help="Directory for storing output files and logs (default: auto-generated in current directory)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Get research goal either from command line arguments or from a file
    user_research_goal = ""
    if args.research_goal:
        # Join research goal words if provided as command line arguments
        user_research_goal = " ".join(args.research_goal)
    elif args.goal_file:
        # Read research goal from specified file
        try:
            if not os.path.exists(args.goal_file):
                print(f"Error: File not found: {args.goal_file}")
                sys.exit(1)
                
            with open(args.goal_file, 'r', encoding='utf-8') as f:
                user_research_goal = f.read().strip()
                
            if not user_research_goal:
                print(f"Error: File is empty: {args.goal_file}")
                sys.exit(1)
                
            print(f"Research goal loaded from file: {args.goal_file}")
        except Exception as e:
            print(f"Error loading research goal from file {args.goal_file}: {e}")
            sys.exit(1)
    
    # Validate research goal
    if not user_research_goal:
        print("Error: Research goal cannot be empty")
        sys.exit(1)
    
    # Calculate reasonable min/max idea bounds based on initial count if not provided
    min_ideas = args.min_ideas if args.min_ideas is not None else max(15, args.initial_ideas-5)
    max_ideas = args.max_ideas if args.max_ideas is not None else max(30, args.initial_ideas+10)

    # Update debugging mode if requested
    global DEBUG_MODE
    if args.debug:
        DEBUG_MODE = True
        print("Debug logging enabled")

    # Initialize both clients with the selected models
    global main_client, reflection_client, MAIN_MODEL_ID, REFLECTION_MODEL_ID, MODEL_CONFIG, MODEL_ID, client
    main_client, MAIN_MODEL_ID, main_config = initialize_client(args.model, is_reflection=False)
    
    # Use reflection model if specified, otherwise use main model
    reflection_model = args.reflection_model if args.reflection_model else args.model
    reflection_client, REFLECTION_MODEL_ID, reflection_config = initialize_client(reflection_model, is_reflection=True)
    
    # For backward compatibility, also set the client and MODEL_ID variables
    client = main_client
    MODEL_ID = MAIN_MODEL_ID
    MODEL_CONFIG = main_config
    
    print(f"Generating {args.initial_ideas} ideas for research goal: {user_research_goal}")
    print(f"Allowing {args.new_per_round} new ideas per round")
    print(f"Will report top {args.final_ideas} ideas in final output")
    print(f"Idea bounds: min={min_ideas}, max={max_ideas} (adjustable via --min-ideas and --max-ideas)")
    print(f"Using main model: {args.model} ({MAIN_MODEL_ID})")
    if args.reflection_model:
        print(f"Using reflection model: {args.reflection_model} ({REFLECTION_MODEL_ID})")
        
    # Run the main workflow
    run_co_scientist_workflow(
        research_goal=user_research_goal,
        num_initial_ideas=args.initial_ideas,
        max_new_ideas_per_round=args.new_per_round,
        min_ideas=min_ideas,
        max_ideas=max_ideas,
        num_final_ideas=args.final_ideas,
        output_dir=args.output_dir
    )

