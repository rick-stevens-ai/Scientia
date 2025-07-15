"""
Scientia: AI-driven scientific idea generation and evaluation system.

This is the main entry point for the Scientia system. It orchestrates the
workflow for generating, evaluating, and refining scientific ideas.
"""

import sys
import os
import time
import traceback
import argparse
import textwrap
import pickle
import datetime
import random
import re
from typing import List, Dict, Any, Tuple, Optional, Set

from openai import OpenAI
from openai import APIError, APITimeoutError, APIConnectionError, RateLimitError

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
                                formatted_evaluation += f"This idea represents


        if file_size_after <= file_size_before:
            print(f"Error: Failed to verify file size increased after append: {file_path}")
            return False
            
        log_debug(f"File appended and verified: {file_path}")
        return True
    except Exception as e:
        print(f"Error appending to file {file_path}: {e}")
        traceback.print_exc()
        return False

def create_scientia_directory(problem_name: str) -> Optional[str]:
    """
    Create a .scientia directory for the problem with versioning.
    
    Args:
        problem_name: Base name for the directory
        
    Returns:
        Absolute path to the created directory, or None if failed
    """
    # Use absolute path
    current_dir = os.getcwd()
    base_dir_name = f"{problem_name}.scientia"
    base_dir = os.path.join(current_dir, base_dir_name)
    
    # Check if directory already exists
    if not os.path.exists(base_dir):
        if create_directory(base_dir):
            # Create a marker file to verify persistence
            marker_file = os.path.join(base_dir, ".marker")
            try:
                with open(marker_file, 'w') as f:
                    f.write(f"Created: {datetime.datetime.now().isoformat()}")
                if os.path.exists(marker_file):
                    print(f"Created directory: {base_dir}")
                    return base_dir
                else:
                    print(f"Error: Failed to verify marker file creation in {base_dir}")
                    return None
            except Exception as e:
                print(f"Error creating marker file: {e}")
                traceback.print_exc()
                return None
        else:
            return None
    
    # Find the next available version number
    version = 1
    while os.path.exists(os.path.join(current_dir, f"{base_dir_name}.{version}")):
        version += 1
    
    versioned_dir = os.path.join(current_dir, f"{base_dir_name}.{version}")
    
    if create_directory(versioned_dir):
        # Create a marker file to verify persistence
        marker_file = os.path.join(versioned_dir, ".marker")
        try:
            with open(marker_file, 'w') as f:
                f.write(f"Created: {datetime.datetime.now().isoformat()}")
            if os.path.exists(marker_file):
                print(f"Created versioned directory: {versioned_dir}")
                return versioned_dir
            else:
                print(f"Error: Failed to verify marker file creation in {versioned_dir}")
                return None
        except Exception as e:
            print(f"Error creating marker file: {e}")
            traceback.print_exc()
        return None
    else:
        return None

##############################################################################
# Logging and Tracking Functions
##############################################################################

def extract_idea_specific_feedback(feedback_text: str, idea_num: int, total_ideas: int, idea_text: str = "") -> str:
    """
    Extract feedback specific to a single idea from a comprehensive feedback text.
    
    Args:
        feedback_text: The complete feedback text for all ideas
        idea_num: The idea number to extract feedback for (1-based)
        total_ideas: Total number of ideas in the feedback
        idea_text: Optional text of the idea to help match content
        
    Returns:
        Extracted feedback specific to the requested idea
    """
    try:
        # If specific idea markers are detected in the feedback, use them
        # Look for specific section headers about this idea
        idea_patterns = [
            # More specific patterns first
            fr'(?i)(?:^|\n)(?:##+ *)?{idea_num}\. +(?:[^#\n]+)(?:\n|$).*?(?=(?:^|\n)(?:##+ *)?(?:{idea_num+1}|[^{idea_num}])\. +|\Z)',  # Numbered heading
            fr'(?i)(?:^|\n)(?:##+ *)?Idea *{idea_num}[:.] *(?:[^#\n]+)(?:\n|$).*?(?=(?:^|\n)(?:##+ *)?Idea *(?:{idea_num+1}|[^{idea_num}])[:.] *|\Z)',  # "Idea N:" heading
            fr'(?i)(?:^|\n)\| *{idea_num} *\|.*?(?=(?:^|\n)\| *(?:{idea_num+1}|[^{idea_num}]) *\||\Z)',  # Table row for idea N
            fr'(?i)(?:^|\n)(?:Analysis|Review|Evaluation|Assessment|Feedback) (?:of|for) (?:Idea|Hypothesis) *{idea_num}[:.] *(?:[^#\n]+)(?:\n|$).*?(?=(?:^|\n)(?:Analysis|Review|Evaluation|Assessment|Feedback) (?:of|for) (?:Idea|Hypothesis) *(?:{idea_num+1}|[^{idea_num}])[:.] *|\Z)',  # Analysis for Idea N
        ]
        
        for pattern in idea_patterns:
            matches = re.finditer(pattern, feedback_text, re.DOTALL)
            for match in matches:
                extracted_text = match.group(0).strip()
                if len(extracted_text) > 50:  # Longer minimum to ensure meaningful content
                    return extracted_text
        
        # If we couldn't find a specific pattern, try other patterns that might indicate idea-specific sections
        # Look for sections that mention the idea number
        mention_patterns = [
            fr'(?i)(?:^|\n)(?:.*?Idea *{idea_num}.*?)(?:\n|$).*?(?=\n[A-Z#]|\Z)',  # Any paragraph mentioning "Idea N"
            fr'(?i)(?:^|\n)(?:.*?#{idea_num}.*?)(?:\n|$).*?(?=\n[A-Z#]|\Z)',  # Any paragraph mentioning "#N"
        ]
        
        for pattern in mention_patterns:
            matches = re.finditer(pattern, feedback_text, re.DOTALL)
            for match in matches:
                extracted_text = match.group(0).strip()
                if len(extracted_text) > 50:
                    return extracted_text
        
        # Try to find sections that contain keywords from the idea title/key idea
        # This requires the idea text to be passed in, but we don't have it here...
        
        # If we still couldn't find specific content, look for general sections that apply to all ideas
        general_patterns = [
            r"(?i)(?:^|\n)Summary (?:Table|of (?:all )?ideas).*?(?=\n##|\Z)",
            r"(?i)(?:^|\n)General (?:Recommendations|Feedback|Analysis).*?(?=\n##|\Z)",
            r"(?i)(?:^|\n)Overall (?:Assessment|Evaluation|Analysis).*?(?=\n##|\Z)",
            r"(?i)(?:^|\n)Comparison (?:of Ideas|Table|Matrix).*?(?=\n##|\Z)",
        ]
        
        for pattern in general_patterns:
            matches = re.finditer(pattern, feedback_text, re.DOTALL)
            for match in matches:
                general_text = match.group(0).strip()
                if len(general_text) > 100:  # Higher threshold for general sections
                    return f"General feedback (applies to all ideas):\n\n{general_text}"
        
        # If nothing else, try to extract any section with a reasonable length that might be relevant
        fallback_sections = re.split(r'\n(?:##+ |\d+\. )', feedback_text)
        relevant_sections = []
        
        for section in fallback_sections:
            if len(section) > 200 and section.strip():  # Only consider substantial sections
                relevant_sections.append(section.strip())
        
        if relevant_sections:
            # Take the first substantial section as a fallback
            return f"General feedback extracted (may apply to multiple ideas):\n\n{relevant_sections[0]}"
        
        # Last resort: return a note about no specific feedback
        return f"Note: No specific feedback found for Idea {idea_num} in the analyzer output."
        
    except Exception as e:
        print(f"Error extracting idea-specific feedback: {e}")
        traceback.print_exc()
        return feedback_text  # If extraction fails, return the full text as a fallback

def log_idea(scientia_dir: str, idea_num: int, idea_text: str, phase: str, 
             round_num: Optional[int] = None, elo_score: Optional[float] = None,
             unique_id: Optional[str] = None, metadata: Optional[IdeaMetadata] = None) -> bool:
    """
    Log an idea's current state to its dedicated log file.
    Each idea has its own log file that is appended to throughout the process.
    
    Args:
        scientia_dir: Path to the .scientia directory
        idea_num: The idea's number/ID
        idea_text: The current text/content of the idea
        phase: Current phase (e.g., "Initial Generation", "Evolution", "Tournament")
        round_num: Current round number (if applicable)
        elo_score: Current ELO score (if applicable)
        unique_id: Unique identifier for the idea (if available)
        metadata: IdeaMetadata object for the idea (if available)
        
    Returns:
        True if logging was successful, False otherwise
    """
    try:
        # Create the standard log file (for backward compatibility)
        log_file = os.path.join(scientia_dir, f"idea_{idea_num}.log")
        
        # Create a unique ID-based file name if available
        unique_log_file = None
        if unique_id:
            unique_log_file = os.path.join(scientia_dir, f"idea_{unique_id}.md")
        
        # Prepare log entry with timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "phase": phase,
            "round": round_num,
            "elo_score": elo_score,
            "content": idea_text
        }
        
        # Append to existing log or create new file (standard log)
        header = f"{'=' * 80}\n"
        header += f"TIMESTAMP: {timestamp}\n"
        header += f"PHASE: {phase}"
        if round_num is not None:
            header += f", ROUND: {round_num}"
        if elo_score is not None:
            header += f", ELO SCORE: {elo_score:.1f}"
        if unique_id is not None:
            header += f"\nUNIQUE_ID: {unique_id}"
        header += f"\n{'=' * 80}\n\n"
        entry = header + idea_text + "\n\n"
        
        # Log to standard log file
        standard_log_success = False
        if os.path.exists(log_file):
            standard_log_success = append_file(log_file, entry)
        else:
            standard_log_success = write_file(log_file, f"IDEA {idea_num} EVOLUTION LOG\n\n" + entry)
        
        # If unique ID is provided, also log to a dedicated markdown file
        unique_log_success = True  # Default to true if not applicable
        if unique_log_file:
            # Format the entry as a nicer markdown document
            md_header = f"# Idea {idea_num}: Evolution Log\n\n"
            if metadata and hasattr(metadata, 'unique_id'):
                md_header += f"**Unique ID:** {metadata.unique_id}\n\n"
            
            md_entry = f"## {phase}"
            if round_num is not None:
                md_entry += f" (Round {round_num})"
            md_entry += f"\n\n**Timestamp:** {timestamp}\n\n"
            
            if elo_score is not None:
                md_entry += f"**ELO Score:** {elo_score:.1f}\n\n"
                
            # Add criteria scores if available
            if metadata and hasattr(metadata, 'criteria_scores') and metadata.criteria_scores:
                md_entry += "**Scientific Criteria Scores:**\n\n"
                for criterion, score in metadata.criteria_scores.items():
                    md_entry += f"- {criterion}: {score:.1f}\n"
                md_entry += "\n"
                
            md_entry += "**Content:**\n\n"
            md_entry += idea_text + "\n\n"
            md_entry += "---\n\n"  # Separator between entries
            
            if os.path.exists(unique_log_file):
                unique_log_success = append_file(unique_log_file, md_entry)
            else:
                unique_log_success = write_file(unique_log_file, md_header + md_entry)
                
        return standard_log_success and unique_log_success
            
    except Exception as e:
        print(f"Error logging idea {idea_num}: {e}")
        traceback.print_exc()
        return False

def is_significant_change(original_idea: str, refined_idea: str, threshold: float = 0.4) -> bool:
    """
    Determine if the refinement to an idea represents a significant change.
    
    Args:
        original_idea: The original idea text
        refined_idea: The refined idea text
        threshold: The similarity threshold below which we consider a change significant
        
    Returns:
        True if the change is significant, False otherwise
    """
    # Parse the structured sections
    original_sections = parse_structured_idea(original_idea)
    refined_sections = parse_structured_idea(refined_idea)
    
    # Check if the key_idea has changed significantly
    original_key = original_sections.get("key_idea", "").lower()
    refined_key = refined_sections.get("key_idea", "").lower()
    
    # If the key idea is completely different, it's significant
    if original_key and refined_key and len(original_key) > 10 and len(refined_key) > 10:
        # Simple similarity check: what fraction of words in the original 
        # are also in the refinement
        original_words = set(original_key.split())
        refined_words = set(refined_key.split())
        
        if len(original_words) == 0:
            return True
            
        common_words = original_words.intersection(refined_words)
        similarity = len(common_words) / len(original_words)
        
        # If similarity is below threshold, it's a significant change
        if similarity < threshold:
            return True
    
    # Check if the approach has changed significantly
    original_approach = original_sections.get("approach", "").lower()
    refined_approach = refined_sections.get("approach", "").lower()
    
    if original_approach and refined_approach and len(original_approach) > 20 and len(refined_approach) > 20:
        # Simple approach similarity check
        original_words = set(original_approach.split())
        refined_words = set(refined_approach.split())
        
        if len(original_words) == 0:
            return True
            
        common_words = original_words.intersection(refined_words)
        approach_similarity = len(common_words) / len(original_words)
        
        # If approach similarity is below threshold, it's a significant change
        if approach_similarity < threshold:
            return True
    
    # Default: not a significant change
    return False

def extract_citations(text: str) -> List[str]:
    """Extract citations in [Author Year] format from text."""
    citation_pattern = r'\[(.*?\s+\d{4}(?:;\s*.*?\s+\d{4})*)\]'
    citations = re.findall(citation_pattern, text)
    unique_citations = set()
    for citation_group in citations:
        for single_citation in re.split(r';\s*', citation_group):
            unique_citations.add(single_citation.strip())
    return sorted(list(unique_citations))

def parse_structured_idea(idea_text: str) -> Dict[str, str]:
    """
    Parse a structured idea text into its component parts.
    
    Args:
        idea_text: Text of a single idea with structured sections
        
    Returns:
        Dictionary with keys for each section: title, key_idea, paragraph, approach, references
    """
    sections = {
        "title": "",
        "key_idea": "",
        "paragraph": "",
        "approach": "",
        "references": ""
    }
    
    # First try the exact headers we expect
    title_pattern = r'(?:\*\*)?Title(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Key Idea(?:\*\*)?:?|$)'
    key_idea_pattern = r'(?:\*\*)?Key Idea(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Paragraph(?:\*\*)?:?|$)'
    paragraph_pattern = r'(?:\*\*)?Paragraph(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Approach(?:\*\*)?:?|$)'
    approach_pattern = r'(?:\*\*)?Approach(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Key References(?:\*\*)?:?|$)'
    references_pattern = r'(?:\*\*)?Key References(?:\*\*)?:?\s*(.*?)$'
    
    # Look for section headers in the text
    title_match = re.search(title_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    key_idea_match = re.search(key_idea_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    paragraph_match = re.search(paragraph_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    approach_match = re.search(approach_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    references_match = re.search(references_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    # If we can't find the exact headers, try alternative headers that might be used
    if not title_match:
        title_match = re.search(r'(?:\*\*)?(?:Title|Heading|Name|Topic)(?:\*\*)?:?\s*(.*?)(?=\n|$)', idea_text, re.IGNORECASE | re.DOTALL)
    
    if not key_idea_match:
        key_idea_match = re.search(r'(?:\*\*)?(?:Key Idea|Hypothesis|Core Idea|Main Idea)(?:\*\*)?:?\s*(.*?)(?=\n|$)', idea_text, re.IGNORECASE | re.DOTALL)
    
    if not paragraph_match:
        paragraph_match = re.search(r'(?:\*\*)?(?:Paragraph|Summary|Description|Explanation|Background)(?:\*\*)?:?\s*(.*?)(?=\n|$)', idea_text, re.IGNORECASE | re.DOTALL)
        
    if not approach_match:
        approach_match = re.search(r'(?:\*\*)?(?:Approach|Methods|Testing|Implementation|Methodology)(?:\*\*)?:?\s*(.*?)(?=\n|$)', idea_text, re.IGNORECASE | re.DOTALL)
    
    if not references_match:
        references_match = re.search(r'(?:\*\*)?(?:Key References|References|Citations|Bibliography)(?:\*\*)?:?\s*(.*?)(?=\n|$)', idea_text, re.IGNORECASE | re.DOTALL)
    
    # Extract and clean each section
    # Extract and clean each section
    if title_match:
        sections["title"] = title_match.group(1).strip()
    if key_idea_match:
        sections["key_idea"] = key_idea_match.group(1).strip()
    if paragraph_match:
        sections["paragraph"] = paragraph_match.group(1).strip()
    if approach_match:
        sections["approach"] = approach_match.group(1).strip()
    if references_match:
        sections["references"] = references_match.group(1).strip()
    
    # If we couldn't find structured sections, use the whole text as the key_idea
    if not any(sections.values()):
        sections["key_idea"] = idea_text.strip()
    
    return sections

def format_structured_idea(sections: Dict[str, str]) -> str:
    """
    Format a structured idea from its component sections.
    
    Args:
        sections: Dictionary with keys for each section
        
    Returns:
        Formatted idea text with all sections
    """
    formatted = ""
    if sections.get("title"):
        formatted += f"**Title**: {sections['title']}\n\n"
    if sections.get("key_idea"):
        formatted += f"**Key Idea**: {sections['key_idea']}\n\n"
    if sections.get("paragraph"):
        formatted += f"**Paragraph**: {sections['paragraph']}\n\n"
    if sections.get("approach"):
        formatted += f"**Approach**: {sections['approach']}\n\n"
    if sections.get("references"):
        formatted += f"**Key References**: {sections['references']}\n\n"
    
    return formatted.strip()

def parse_ideas_from_text(text: str, expected_count: int) -> List[str]:
    """
    Extract individual numbered ideas from a text output and format them consistently.
    
    Args:
        text: Text containing numbered ideas (e.g., "1. Idea one", "2. Idea two", etc.)
            or research ideas (e.g., "Research Idea 1: ...")
        expected_count: Expected number of ideas to extract
        
    Returns:
        List of extracted ideas as strings, formatted with consistent structure
    """
    try:
        # First, try to match "Research Idea N:" format
        research_pattern = r'(?:\n|^)\s*(?:\*\*)?Research Idea (\d+)(?:\*\*)?:?\s*(.*?)(?=(?:\n|^)\s*(?:\*\*)?Research Idea \d+(?:\*\*)?:?|\Z)'
        research_matches = list(re.finditer(research_pattern, text, re.DOTALL | re.IGNORECASE))
        
        if research_matches:
            ideas = []
            for match in research_matches:
                idea_text = match.group(2).strip()
                if idea_text:
                    # Parse the structured sections and reformat
                    sections = parse_structured_idea(idea_text)
                    ideas.append(format_structured_idea(sections))
            
            if ideas:
                return _verify_idea_count(ideas, expected_count)
        
        # If no research ideas found, try standard numbered list (1., 2., etc.)
        idea_pattern = r'(?:\n|^)\s*(\d+)\.\s+(.*?)(?=\n\s*\d+\.\s+|\Z)'
        matches = list(re.finditer(idea_pattern, text, re.DOTALL))
        
        if matches:
            ideas = []
            for match in matches:
                idea_text = match.group(2).strip()
                if idea_text:
                    # Parse the structured sections and reformat
                    sections = parse_structured_idea(idea_text)
                    ideas.append(format_structured_idea(sections))
            
            if ideas:
                return _verify_idea_count(ideas, expected_count)
        
        # Try to identify structured ideas based on their section headers
        structured_idea_pattern = r'(?:\n|^)\s*(?:\*\*)?Title(?:\*\*)?:?\s*(.*?)(?:\n|^)(?:\s*(?:\*\*)?Key Idea(?:\*\*)?:?)'
        structured_matches = list(re.finditer(structured_idea_pattern, text, re.DOTALL | re.IGNORECASE))
        
        if structured_matches:
            # If we found structured ideas, split the text at each "Title:" marker
            split_points = [match.start() for match in structured_matches]
            split_points.append(len(text))  # Add end of text
            
            ideas = []
            for i in range(len(split_points) - 1):
                idea_text = text[split_points[i]:split_points[i+1]].strip()
                if idea_text:
                    # Parse the structured sections and reformat
                    sections = parse_structured_idea(idea_text)
                    ideas.append(format_structured_idea(sections))
            
            if ideas:
                return _verify_idea_count(ideas, expected_count)
        
        # If still no ideas found, try to split by bold titles or headings
        title_pattern = r'(?:\n|^)\s*(?:\*\*|#+ )(.*?)(?:\*\*|:)'
        title_matches = list(re.finditer(title_pattern, text, re.DOTALL))
        
        if title_matches:
            split_points = [match.start() for match in title_matches]
            split_points.append(len(text))  # Add end of text
            
            ideas = []
            for i in range(len(split_points) - 1):
                idea_text = text[split_points[i]:split_points[i+1]].strip()
                if idea_text:
                    sections = parse_structured_idea(idea_text)
                    ideas.append(format_structured_idea(sections))
            
            if ideas:
                return _verify_idea_count(ideas, expected_count)
        
        # Last resort: try to split the text by empty lines or section breaks
        if not ideas:
            # Split by multiple newlines (indicating paragraph breaks)
            sections = re.split(r'\n\s*\n', text)
            raw_ideas = [section.strip() for section in sections if section.strip()]
            
            # If we got too many sections, try to filter likely ideas
            if len(raw_ideas) > expected_count * 2:
                # Filter to sections that contain keywords related to our structured format
                structured_ideas = [idea for idea in raw_ideas if re.search(r'(?i)title|key idea|hypothesis|approach|references', idea)]
                if structured_ideas and len(structured_ideas) <= expected_count * 2:
                    raw_ideas = structured_ideas
            
            # Group sections into expected_count ideas
            ideas = []
            if raw_ideas:
                # If we have exactly the expected number, use them directly
                if len(raw_ideas) == expected_count:
                    for idea_text in raw_ideas:
                        sections = parse_structured_idea(idea_text)
                        ideas.append(format_structured_idea(sections))
                # Otherwise try to group them logically
                else:
                    sections_per_idea = max(1, len(raw_ideas) // expected_count)
                    for i in range(0, min(len(raw_ideas), expected_count * sections_per_idea), sections_per_idea):
                        combined_sections = "\n\n".join(raw_ideas[i:i+sections_per_idea])
                        parsed_sections = parse_structured_idea(combined_sections)
                        ideas.append(format_structured_idea(parsed_sections))
                        if len(ideas) >= expected_count:
                            break
            
            if ideas:
                return _verify_idea_count(ideas, expected_count)
        
        # If still no ideas, return placeholders
        print(f"Warning: Failed to parse any ideas using available patterns.")
        placeholder_ideas = []
        for i in range(expected_count):
            placeholder = {
                "title": f"Placeholder Idea {i+1}",
                "key_idea": "Please review generation output manually.",
                "paragraph": "This is a placeholder for an idea that couldn't be parsed automatically.",
                "approach": "Manual review required.",
                "references": "[Author Year]"
            }
            placeholder_ideas.append(format_structured_idea(placeholder))
        return placeholder_ideas
    except Exception as e:
        print(f"Error parsing ideas from text: {e}")
        traceback.print_exc()
        
        # Return placeholder ideas if parsing fails
        placeholder_ideas = []
        for i in range(expected_count):
            placeholder = {
                "title": f"Placeholder Idea {i+1}",
                "key_idea": "Please review generation output manually.",
                "paragraph": "This is a placeholder for an idea that couldn't be parsed automatically.",
                "approach": "Manual review required.",
                "references": "[Author Year]"
            }
            placeholder_ideas.append(format_structured_idea(placeholder))
        return placeholder_ideas

def _verify_idea_count(ideas: List[str], expected_count: int) -> List[str]:
    """Helper function to verify and adjust the number of ideas."""
    if len(ideas) != expected_count:
        print(f"Warning: Expected {expected_count} ideas, but found {len(ideas)}.")
        # If we found more ideas than expected, trim the list
        if len(ideas) > expected_count:
            print(f"Trimming to the first {expected_count} ideas.")
            ideas = ideas[:expected_count]
        # If we found fewer, log the issue
        else:
            print("Proceeding with fewer ideas than expected.")
    return ideas

def parse_ideas_order_from_ranking(ranking_output: str, ideas: List[str]) -> List[str]:
    """
    Reorder ideas based on ranking output.
    
    Args:
        ranking_output: Text containing ranking information
        ideas: Original list of ideas to be reordered
        
    Returns:
        Reordered list of ideas based on the ranking
    """
    try:
        # Look for lines that start with a number and indicate ranking
        # e.g., "1.", "Rank #1:", "1)", etc.
        rank_pattern = r'(?:\n|^)\s*(?:rank\s*#?\s*)?(\d+)[\.:\)]\s*(.*?)(?=\n\s*(?:rank\s*#?\s*)?\d+[\.:\)]|\Z)'
        matches = re.finditer(rank_pattern, ranking_output, re.DOTALL | re.IGNORECASE)
        
        # Create mapping from original ideas to their new positions
        ranking_map = {}
        for match in matches:
            rank = int(match.group(1))
            description = match.group(2).strip()
            
            # Find which idea this rank refers to by looking for key phrases in the description
            for i, idea in enumerate(ideas):
                # Extract first 10-15 words from the idea for matching
                idea_start = ' '.join(idea.split()[:15]).lower()
                desc_lower = description.lower()
                
                # Check if the description contains enough of the idea to identify it
                # We look for the first few words or a significant substring
                if idea_start[:30] in desc_lower or any(phrase in desc_lower for phrase in idea_start.split('.')[:2]):
                    ranking_map[i] = rank - 1  # Zero-indexed position
                    break
        
        # If we couldn't match ideas to rankings, return the original order
        if not ranking_map:
            print("Warning: Could not parse ranking order. Maintaining original order.")
            return ideas
            
        # Create a new ordered list
        ordered_ideas = [None] * len(ideas)
        used_positions = set()
        
        # Place ideas in their ranked positions
        for orig_idx, new_idx in ranking_map.items():
            if new_idx < len(ideas) and new_idx not in used_positions:
                ordered_ideas[new_idx] = ideas[orig_idx]
                used_positions.add(new_idx)
        
        # Fill in any gaps with unranked ideas
        unranked_ideas = [idea for i, idea in enumerate(ideas) if i not in ranking_map]
        for i in range(len(ordered_ideas)):
            if ordered_ideas[i] is None and unranked_ideas:
                ordered_ideas[i] = unranked_ideas.pop(0)
        
        # Return the reordered list, falling back to original if something went wrong
        if None in ordered_ideas:
            print("Warning: Ranking reordering incomplete. Some ideas couldn't be placed.")
            # Replace None values with any remaining unranked ideas
            for i in range(len(ordered_ideas)):
                if ordered_ideas[i] is None and unranked_ideas:
                    ordered_ideas[i] = unranked_ideas.pop(0)
                    
            # If there are still None values, use original ideas
            if None in ordered_ideas:
                remaining_ideas = [idea for idea in ideas if idea not in ordered_ideas]
                for i in range(len(ordered_ideas)):
                    if ordered_ideas[i] is None and remaining_ideas:
                        ordered_ideas[i] = remaining_ideas.pop(0)
        
        # Final check to ensure we didn't lose any ideas
        if len(ordered_ideas) != len(ideas) or None in ordered_ideas:
            print("Warning: Error in reordering. Reverting to original order.")
            return ideas
            
        return ordered_ideas
        
    except Exception as e:
        return ideas
        
def is_valid_idea(idea: str) -> bool:
    """Check if an idea is valid and complete for tournament comparison."""
    # Basic length check - very minimal to allow most reasonable ideas
    if not idea or len(idea.strip()) < 20:
        return False
        
    # Parse the idea structure
    sections = parse_structured_idea(idea)
    
    # More flexible validation - accept ideas if they have any meaningful content
    # Either have a key_idea or the idea text itself is substantial
    if sections.get("key_idea") or (len(idea) > 100 and "**" in idea):
        return True
        
    # Check for certain keywords that indicate a substantive idea
    idea_lower = idea.lower()
    keywords = ["hypothesis", "approach", "method", "technique", "strategy", 
               "propose", "develop", "implement", "optimize", "culture", "growth"]
    if any(keyword in idea_lower for keyword in keywords):
        return True
        
    # Final fallback - if the idea has multiple paragraphs and reasonable length, accept it
    paragraphs = [p for p in idea.split('\n\n') if p.strip()]
    if len(paragraphs) >= 2 and len(idea) > 200:
        return True
        
    return False

def calculate_vector_score(scores_a: IdeaScore, scores_b: IdeaScore) -> float:
    '''
    Calculate a normalized score between two ideas based on their vector scores.
    Returns a value between 0 and 1 representing idea_a's performance vs idea_b.
    '''
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
    
def calculate_elo_update(rating_a: float, rating_b: float, score: float, k: float = 64.0) -> Tuple[float, float]:
    '''
    Calculate updated ELO ratings based on the comparison score.
    score should be between 0 and 1, representing idea_a's performance against idea_b.
    '''
    expected_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
    update = k * (score - expected_a)
    return rating_a + update, rating_b - update

def generate_final_report(scientia_dir: str, idea_num: int, idea_text: str, 
                         final_elo: float, log_file_path: str, idea_tracker: Optional[IdeaEvolution] = None) -> bool:
    """
    Generate a comprehensive final report for an idea in markdown format.
    
    Args:
        scientia_dir: Path to the .scientia directory
        idea_num: The idea's number/ID
        idea_text: The final version of the idea
        final_elo: The final ELO score
        log_file_path: Path to the idea's log file
        idea_tracker: Optional IdeaEvolution instance for accessing criteria scores
        
    Returns:
        True if report was generated successfully, False otherwise
    """
    try:
        report_file = os.path.join(scientia_dir, f"idea_{idea_num}_final.md")
        
        # Find idea's metadata and unique ID if available
        idea_metadata = None
        idea_unique_id = None
        criteria_scores = {}
        
        if idea_tracker:
            # Look for this idea in the tracker
            for id, text in idea_tracker.get_all_ideas().items():
                if text == idea_text:
                    idea_metadata = idea_tracker.get_metadata(id)
                    idea_unique_id = getattr(idea_metadata, "unique_id", None)
                    criteria_scores = getattr(idea_metadata, "criteria_scores", {}) or {}
                    break
        
        # Extract citations from the idea text
        citations = extract_citations(idea_text)
        
        # Parse the structured sections of the idea
        sections = parse_structured_idea(idea_text)
        
        # Read the evolution history from the log file
        evolution_history = []
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
            
            # Split log into entries by the separator
            entries = log_content.split("="*80)
            
            # Process each entry
            for entry in entries:
                if entry.strip():
                    # Parse timestamps, phases, and content
                    timestamp_match = re.search(r'TIMESTAMP: (.*?)$', entry, re.MULTILINE)
                    phase_match = re.search(r'PHASE: (.*?)(?:, ROUND:|, ELO SCORE:|$)', entry, re.MULTILINE)
                    round_match = re.search(r'ROUND: (\d+)', entry)
                    elo_match = re.search(r'ELO SCORE: (\d+\.\d+)', entry)
                    unique_id_match = re.search(r'UNIQUE_ID: (.*?)$', entry, re.MULTILINE)
                    
                    # Skip header entry (first entry might be just the header)
                    if timestamp_match and phase_match:
                        timestamp = timestamp_match.group(1).strip()
                        phase = phase_match.group(1).strip()
                        round_num = int(round_match.group(1)) if round_match else None
                        elo_score = float(elo_match.group(1)) if elo_match else None
                        entry_unique_id = unique_id_match.group(1).strip() if unique_id_match else None
                        
                        # Extract content after the metadata section
                        content_parts = entry.split("\n\n", 1)
                        content = content_parts[1] if len(content_parts) > 1 else ""
                        
                        evolution_history.append({
                            "timestamp": timestamp,
                            "phase": phase,
                            "round": round_num,
                            "elo_score": elo_score,
                            "unique_id": entry_unique_id,
                            "content": content.strip()
                        })
        
        # Generate the report content with structured sections
        report_content = f"""# Final Report: Idea {idea_num}

## Title

{sections.get("title", "Untitled")}

## One Sentence Summary

{sections.get("key_idea", "No summary available")}

## Paragraph Summary

{sections.get("paragraph", "No detailed summary available")}

## Final ELO Score and Rank

**Final ELO Score:** {final_elo:.1f}

## Scientific Criteria Ratings

"""
        
        # Add criteria scores in a table
        if criteria_scores:
            report_content += "| Criterion | Score |\n|---|---:|\n"
            for criterion in TOURNAMENT_CRITERIA:
                score = criteria_scores.get(criterion, 0.0)
                report_content += f"| {criterion} | {score:.1f}/10 |\n"
        else:
            report_content += "No detailed ratings available.\n\n"
        
        # Add key idea implementation details
        report_content += """
## Key Ideas and Implementation

This section provides a detailed explanation of the key ideas and how they could be implemented or tested.

"""
        # Add approach and details
        if sections.get("approach"):
            report_content += f"### Implementation and Testing Approach\n\n{sections['approach']}\n\n"
        
        # Add annotations for references
        report_content += """
## Detailed Bibliography with Relevance Annotations

The following references are relevant to this idea:

"""
        
        # If we have citations, list them with relevance notes
        if citations:
            for citation in citations:
                report_content += f"- **{citation}**: Relevant to the core concepts of this idea, providing theoretical foundation and empirical evidence.\n"
        else:
            report_content += "No specific citations were provided for this idea.\n\n"
        
        # Add evolution history with more detail
        report_content += "## Complete Evolution History\n\n"
        report_content += "This section documents the complete evolution of the idea through each phase of the research process.\n\n"
        
        # Group history entries by phase for a more organized presentation
        phase_groups = {}
        for entry in evolution_history:
            phase = entry["phase"]
            if phase not in phase_groups:
                phase_groups[phase] = []
            phase_groups[phase].append(entry)
        
        # Present history by phase, with entries in chronological order
        for phase, entries in phase_groups.items():
            report_content += f"### {phase} Phase\n\n"
            
            # Sort entries by round number if available
            entries.sort(key=lambda e: e.get("round", 0) or 0)
            
            for i, entry in enumerate(entries):
                round_info = f" (Round {entry['round']})" if entry['round'] is not None else ""
                report_content += f"#### {i+1}. {phase}{round_info}\n"
                report_content += f"**Timestamp:** {entry['timestamp']}\n\n"
                
                if entry['elo_score'] is not None:
                    report_content += f"**ELO Score:** {entry['elo_score']:.1f}\n\n"
                
                # Clean up the content to make it more readable by removing headings and other artifacts
                # This is very basic content cleaning - could be improved
                content = entry['content']
                
                # Extract valuable insights and feedback
                if "Reflection" in phase or "Evaluation" in phase:
                    # For reflection/evaluation, focus on feedback
                    feedback_parts = content.split("---")
                    if len(feedback_parts) > 1:
                        # The feedback is usually after a separator
                        feedback = feedback_parts[-1].strip()
                        report_content += f"**Feedback:**\n\n{feedback}\n\n"
                    else:
                        report_content += f"{content}\n\n"
                elif "Tournament" in phase:
                    # For tournament results, focus on scores and rankings
                    report_content += f"**Tournament Results:**\n\n{content}\n\n"
                else:
                    # For other phases, include the full content
                    report_content += f"{content}\n\n"
                
                report_content += "---\n\n"  # Add separator between entries
        
        # Add comprehensive analysis section
        report_content += "## Comprehensive Analysis\n\n"
        report_content += "This analysis tracks the development of the idea from initial concept through evolution and evaluation.\n\n"
        
        # If there's evaluation data in the history, extract key points
        evaluation_entries = [e for e in evolution_history if "Evaluation" in e["phase"] or "Reflection" in e["phase"]]
        if evaluation_entries:
            report_content += "### Key Insights from Evaluations\n\n"
            for entry in evaluation_entries[-2:]:  # Focus on the most recent evaluations
                report_content += f"- From {entry['phase']}"
                if entry['round'] is not None:
                    report_content += f" (Round {entry['round']})"
                report_content += ": "
                
                # Extract a brief summary from the content
                content = entry['content']
                lines = content.split("\n")
                key_lines = [line for line in lines if line.strip() and len(line) > 30 and not line.startswith("#")]
                if key_lines:
                    report_content += f"{key_lines[0][:150]}...\n"
                else:
                    report_content += "Evaluation provided.\n"
        
        # Write the report to file
        return write_file(report_file, report_content)
    except Exception as e:
        print(f"Error generating final report for idea {idea_num}: {e}")
        traceback.print_exc()
        return False

##############################################################################
##############################################################################
# Checkpoint and Recovery Functions
##############################################################################

def save_checkpoint(scientia_dir: str, checkpoint_name: str, state: Dict[str, Any]) -> bool:
    """
    Save a checkpoint of the current state for potential recovery.
    
    Args:
        scientia_dir: Path to the .scientia directory
        checkpoint_name: Name of the checkpoint
        state: State data to be saved
        
    Returns:
        True on success, False on failure
    """
    if not CHECKPOINT_FREQ or not scientia_dir:
        return True
        
    try:
        checkpoint_file = os.path.join(scientia_dir, f"checkpoint_{checkpoint_name}.pkl")
        with open(checkpoint_file, 'wb') as f:
            pickle.dump(state, f)
            
        log_debug(f"Checkpoint saved: {checkpoint_file}")
        return True
        
    except Exception as e:
        print(f"Error saving checkpoint: {e}")
        traceback.print_exc()
        return False
def load_checkpoint(scientia_dir: str, checkpoint_name: str) -> Optional[Dict[str, Any]]:
    """
    Load a checkpoint of a previous state.
    
    Args:
        scientia_dir: Path to the .scientia directory
        checkpoint_name: Name of the checkpoint
        
    Returns:
        The state from the checkpoint, or None if not found
    """
    if not RECOVERY_ENABLED or not scientia_dir:
        return None
        
    try:
        checkpoint_file = os.path.join(scientia_dir, f"checkpoint_{checkpoint_name}.pkl")
        if not os.path.exists(checkpoint_file):
            return None
            
        with open(checkpoint_file, 'rb') as f:
            state = pickle.load(f)
            
        log_debug(f"Checkpoint loaded: {checkpoint_file}")
        return state
        
    except Exception as e:
        print(f"Error loading checkpoint: {e}")
        traceback.print_exc()
        return None

##############################################################################
# Helper function to call an agent via the OpenAI ChatCompletion API
##############################################################################
# Agent Prompts
##############################################################################


def get_generation_agent_prompt():
    """
    The Generation Agent explores the literature, brainstorms, and synthesizes
    new ideas or hypotheses, ensuring that each idea has a structured format with
    all required sections.
    """
    return (
        "You are the Generation Agent in a multi-agent AI co-scientist system. "
        "You produce new ideas and hypotheses in response to a defined "
        "research goal. For each idea, you MUST include ALL of the following sections in this exact order:\n\n"
        "1. **Title**: A concise, descriptive title for the idea\n"
        "2. **Key Idea**: A single sentence that clearly states the core hypothesis\n"
        "3. **Paragraph**: A detailed explanation that expands on the idea and explains why it's important and unique\n"
        "4. **Approach**: Methods for implementation or testing of the hypothesis\n"
        "5. **Key References**: Relevant citations using the format [Author Year]\n\n"
        "Leverage existing literature, domain knowledge, and "
        "creative thinking to propose multiple distinct research directions, "
        "frameworks, or experimental designs. Strive for novelty, practicality, "
        "and scientific rigor. "
        "Include relevant citations to support your hypotheses and problem descriptions. "
        "If citing specific literature, include brief source details relevant to understanding the "
        "citation's context. These citations should be maintained throughout the "
        "refinement process."
    )
def get_ranking_agent_prompt():
    """
    The Ranking Agent compares and ranks competing hypotheses or proposals,
    considering multiple criteria with emphasis on mathematical, physical,
    and theoretical properties.
    """
    return (
        "You receive multiple research ideas or proposals, each containing an explicit "
        "hypothesis. Compare and rank them based on twenty key criteria: \n\n"
        
        "Core scientific properties:\n"
        "(1) Plausibility - scientific and technical feasibility\n"
        "(2) Theoretical Elegance - simplicity, parsimony, and mathematical beauty\n"
        "(3) Mathematical Rigor - formal mathematical foundation\n"
        "(4) First Principles - derivation from fundamental scientific principles\n"
        "(5) Symmetry Properties - mathematical/physical symmetries and invariants\n"
        "(6) Information Theory - information-theoretic aspects and entropy\n"
        "(7) Predictive Power - ability to make specific, testable predictions\n"
        "(8) Cross-domain Impact - applicability across multiple domains\n\n"
        
        "Theoretical and technical properties:\n"
        "(9) Novelty - uniqueness of the theoretical approach\n"
        "(10) Conceptual Foundations - strength of underlying theoretical basis\n"
        "(11) Systems Properties - emergent behaviors and complexity\n"
        "(12) Energy Efficiency - theoretical energy requirements\n"
        "(13) Conservation Laws - physical conservation principles\n"
        "(14) Dimensional Analysis - mathematical/physical scaling relations\n\n"
        
        "Advanced mathematical properties:\n"
        "(15) Quantum Properties - quantum mechanical considerations\n"
        "(16) Computational Complexity - algorithmic and computational aspects\n"
        "(17) Statistical Mechanics - statistical and ensemble properties\n"
        "(18) Geometric Structure - spatial/temporal geometric properties\n"
        "(19) Phase Transitions - critical phenomena and transitions\n"
        "(20) Dynamical Stability - stability and equilibrium properties\n\n"
        
        "For each idea, evaluate all criteria and provide a final ranking with "
        "detailed rationale emphasizing theoretical and technical merits. Pay "
        "particular attention to mathematical properties, elegance, symmetry, and "
        "foundational principles."
    )
def get_evolution_agent_prompt():
    """
    The Evolution Agent has two main functions: (1) refine existing ideas by simplifying, 
    extending, or combining them with other concepts, and (2) generate entirely new ideas 
    to expand the solution space. Each idea must contain an explicit hypothesis statement
    with appropriate citations.
    """
    return (
        "You are the Evolution Agent in a multi-agent AI co-scientist system. "
        "Your role has three distinct parts:\n\n"
        
        "1. REFINE EXISTING IDEAS (Primary Task):\n"
        "   - For each idea provided, carefully analyze its strengths and potential\n"
        "   - Review any provided reflection feedback for each idea\n"
        "   - Apply one or more of these refinement strategies:\n"
        "     a) Extend the idea with additional components or applications\n"
        "     b) Simplify complex aspects to make implementation more feasible\n"
        "     c) Combine elements from multiple ideas if synergies exist\n"
        "     d) Address identified weaknesses or limitations from reflection feedback\n"
        "   - Each refined idea must maintain its core hypothesis while being stronger\n"
        "   - Preserve all relevant citations and add new ones to support changes\n\n"
        
        "2. SIGNIFICANT IMPROVEMENTS AS NEW IDEAS (Important Task):\n"
        "   - If the reflection feedback suggests a SIGNIFICANT change to an idea's core premise or approach\n"
        "   - Create it as a NEW idea rather than a refinement\n"
        "   - Clearly indicate which original idea it derives from\n"
        "   - Explicitly mention how it differs significantly from the original\n"
        "   - These count toward your total of new ideas generated\n\n"
        
        "3. GENERATE ADDITIONAL NEW IDEAS (Secondary Task):\n"
        "   - After refining existing ideas and creating significant-change new ideas\n"
        "   - Generate additional NEW complementary ideas to meet your target\n"
        "   - These should explore novel angles not covered by existing ideas\n"
        "   - Ensure new ideas maintain the same structured format\n"
        "   - Include multiple relevant citations to support new hypotheses\n\n"
        
        "REQUIRED FORMAT FOR ALL IDEAS (Refined or New):\n"
        "1. **Title**: A concise, descriptive title\n"
        "2. **Key Idea**: Single sentence stating the core hypothesis\n"
        "3. **Paragraph**: Detailed explanation of importance and uniqueness\n"
        "4. **Approach**: Methods for implementation or testing\n"
        "5. **Key References**: Citations in [Author Year] format\n\n"
        
        "For refinements, clearly indicate:\n"
        "- What aspects of the original idea were modified\n"
        "- How the changes strengthen the hypothesis\n"
        "- Any new citations added to support changes\n\n"
        
        "For new ideas based on significant change, clearly indicate:\n"
        "- Which original idea inspired this new direction\n"
        "- How this represents a significant departure from the original\n"
        "- Why this deserves to be a new idea rather than a refinement\n\n"
        
        "For completely new ideas, ensure:\n"
        "- Clear differentiation from existing ideas\n"
        "- Strong theoretical or empirical foundation\n"
        "- Comprehensive citation support\n\n"
        
        "Maintain all existing citations and add new ones where appropriate. "
        "Every hypothesis refinement or new proposal should be well-supported "
        "by citations in [Author Year] format."
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
def get_reflection_agent_prompt():
    """
    The Reflection Agent critically evaluates each idea for plausibility, novelty,
    potential flaws, and citation quality, providing structured feedback.
    """
    return (
        "You are the Reflection Agent in a multi-agent AI co-scientist system. "
        "Analyze each idea's hypothesis and citations for plausibility, novelty, "
        "and potential weaknesses. Provide detailed, structured feedback for "
        "improving each idea."
    )

def get_tournament_agent_prompt():
    """
    The Tournament Agent conducts pairwise comparisons of ideas using
    vector-based scoring across technical and theoretical criteria.
    """
    return (
        "You are the Tournament Agent in a multi-agent AI co-scientist system. "
        "For each pair of ideas, evaluate them across these twenty criteria "
        "and provide numerical scores in EXACTLY this format:\n\n"
        "Criterion 1 (Plausibility): Idea A = X, Idea B = Y\n"
        "Criterion 2 (Theoretical Elegance): Idea A = X, Idea B = Y\n"
        "... (etc. for all 20 criteria)\n\n"
        "Where X and Y are scores between 1-10, where:\n"
        "1: Severely deficient\n"
        "2-3: Poor performance\n"
        "4-5: Below average\n"
        "6: Average\n"
        "7-8: Above average\n"
        "9: Excellent\n"
        "10: Outstanding\n"
    )

def get_meta_review_agent_prompt():
    """
    The Meta-review Agent synthesizes the top-ranked ideas into a cohesive
    overview and final recommendation, focusing on only the best proposals.
    """
    return (
        "You are the Meta-review Agent in a multi-agent AI co-scientist system. "
        "You take the final set of refined, top-ranked research proposals (the "
        "top ideas specified by the user in the final ranking) and compose a meta-analysis: summarize "
        "the core ideas, discuss strengths and limitations, and suggest practical "
        "next steps. Provide a concise but comprehensive overview. "
        "For each of the top ideas, maintain all citations in the format [Author Year]. "
    )

def get_supervisor_agent_prompt():
    """
    The Supervisor Agent manages the overall workflow, coordinates agents, and summarizes each round.
    """
    return (
        "You are the Supervisor Agent in a multi-agent AI co-scientist system. "
        "Your role is to synthesize and integrate feedback from other agents (Reflection, Proximity Check, and Ranking) "
        "into a coherent summary for each round of scientific idea generation and refinement.\n\n"
        "IMPORTANT: You will be provided with the actual outputs from previous agents in your prompt. "
        "You must reference and directly incorporate insights from these outputs in your summary. "
        "Include specific points made by each agent about the ideas being developed, and highlight "
        "common themes, contradictions, or complementary insights across agents.\n\n"
        "Focus on synthesizing the concrete feedback rather than making general statements. "
        "You should discuss how the ideas are evolving based on the specific agent feedback and "
        "identify promising directions for future refinement. Ensure consistency with the actual outputs provided."
    )
##############################################################################

def call_agent(
    agent_system_prompt: str,
    user_prompt: str,
    agent_name: str,
    additional_context: str = "",
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> str:
    '''
    Given an agent-specific system prompt, a user-level prompt, and optional
    additional context (e.g., lists of ideas, feedback from other agents), call
    the OpenAI API to get the agent's response.
    
    Includes retry logic with exponential backoff for handling temporary errors.
    
    Args:
        agent_system_prompt: System prompt defining the agent's role and behavior
        user_prompt: The main user query or instruction
        additional_context: Optional context to include in the conversation
        max_retries: Maximum number of retry attempts on failure
        retry_delay: Initial delay between retries (increases exponentially)
        
    Returns:
        The agent's response text
    '''
    # Select appropriate client and model based on agent type
    if agent_name.lower() == "reflection":
        client_instance = reflection_client
        model_id = REFLECTION_MODEL_ID
    else:
        client_instance = main_client
        model_id = MAIN_MODEL_ID

    messages = [
        {"role": "system", "content": agent_system_prompt},
    ]

    if additional_context:
        messages.append({"role": "assistant", "content": additional_context})

    messages.append({"role": "user", "content": user_prompt})

    # Create a display name from the agent name for output
    agent_display_name = agent_name.title()
    model_display = f" [{model_id}]" if DEBUG_MODE else ""

    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            print(f"Calling {agent_display_name} Agent{model_display}... ", end="", flush=True)
            # For O3 and O4mini models, don't use temperature parameter
            if "o3" in model_id.lower() or "o4" in model_id.lower():
                response = client_instance.chat.completions.create(
                    model=model_id,
                    messages=messages
                )
            else:
                response = client_instance.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.7
                )
            print("✓")
            return response.choices[0].message.content
            
        except APITimeoutError as e:
            if attempt < MAX_RETRIES_TIMEOUT - 1:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                print(f"Timeout error occurred. Retrying ({attempt+1}/{MAX_RETRIES_TIMEOUT}) in {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                print(f"Resuming {agent_display_name} Agent request with longer timeout...")
                # No longer setting timeout directly on the client
                pass
            else:
                print(f"Failed after {MAX_RETRIES_TIMEOUT} timeout retries: {e}")
                raise
                
        except APIConnectionError as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                print(f"Connection error. Retrying in {wait_time:.1f} seconds...")
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
            print(f"Error type: {type(e).__name__}")
            raise
            
        finally:
            # No need to reset timeout anymore since we're not setting it
            pass
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
            ideas_ordered = parse_ideas_order_from_ranking(ranking_output, ideas)
            ideas = ideas_ordered
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
    # Prepare meta-review prompt
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
    
    # Call the meta-review agent
    
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
                    f.write(f"   {idea[:100]}...\n\n")
                
                f.write("\n## Meta-Review\n\n")
                f.write("See the [full meta-review](meta_review.md) for detailed analysis of the top ideas.\n")
            
            print(f"Summary document created: {summary_file}")
        except Exception as e:
            print(f"Warning: Error generating final reports: {e}")
            traceback.print_exc()
    
    
    for i, idea_a in enumerate(ideas):
        print(f"\nIdea {i+1}/{len(ideas)}: Tournament Matchups")
        print("-" * 80)
        match_results[idea_a] = []
        
        # Get possible opponents (excluding self)
        possible_opponents = ideas[:i] + ideas[i+1:]
        opponents = random.sample(possible_opponents, min(num_opponents, len(possible_opponents)))
        
        for match_num, idea_b in enumerate(opponents, 1):
            print(f"\nMatch {match_num}/{len(opponents)}:")
            # Extract and display title for Idea A
            a_sections = parse_structured_idea(idea_a)
            a_title = a_sections.get("title", "")
            print(f"Idea A (current ELO {elo_ratings[idea_a]:.1f}):")
            print(f"  Title: {a_title}")
            print(textwrap.fill(idea_a[:300], width=80, initial_indent="  ", subsequent_indent="  "))
            
            # Extract and display title for Idea B
            b_sections = parse_structured_idea(idea_b)
            b_title = b_sections.get("title", "")
            print(f"\nIdea B (current ELO {elo_ratings[idea_b]:.1f}):")
            print(f"  Title: {b_title}")
            print(textwrap.fill(idea_b[:300], width=80, initial_indent="  ", subsequent_indent="  "))
            
            # Use pre-computed score vectors
            vec_a = score_vectors[idea_a]
            vec_b = score_vectors[idea_b]
            
            # Calculate vector-based score
            match_score = calculate_vector_score(vec_a, vec_b)
            
            # Queue the ELO update
            pending_elo_updates.append((idea_a, idea_b, match_score))
            
            # Store match result for logging
            match_results[idea_a].append({
                'opponent': idea_b,
                'score': match_score,
                'vector_a': vec_a,
                'vector_b': vec_b
            })
            # Log the match details
            # Log the match details
            print(f"Vector-based comparison score: {match_score:.3f}")
            print("\nPre-computed scores by criterion:")
            
            # Print scores for each criterion using the global TOURNAMENT_CRITERIA constant
            for c_idx, (criterion, a_score, b_score) in enumerate(zip(TOURNAMENT_CRITERIA, list(vec_a), list(vec_b))):
                print(f"  {criterion}: A={a_score:.1f}, B={b_score:.1f}")
    # Process all ELO updates in batches
    print("\n=== PROCESSING BATCHED ELO UPDATES ===")
    batch_size = 50  # Process ELO updates in batches of 50 matches
    
    for i in range(0, len(pending_elo_updates), batch_size):
        batch = pending_elo_updates[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(pending_elo_updates) + batch_size - 1)//batch_size}...")
        
        # Track rating changes for this batch
        rating_changes: Dict[str, float] = {}
        
        # Process all matches in the batch
        for idea_a, idea_b, score in batch:
            old_rating_a = elo_ratings[idea_a]
            old_rating_b = elo_ratings[idea_b]
            
            # Calculate rating changes
            new_rating_a, new_rating_b = calculate_elo_update(old_rating_a, old_rating_b, score)
            
            # Accumulate changes
            rating_changes[idea_a] = rating_changes.get(idea_a, 0) + (new_rating_a - old_rating_a)
            rating_changes[idea_b] = rating_changes.get(idea_b, 0) + (new_rating_b - old_rating_b)
        
        # Apply accumulated changes
        print("\n=== ELO RATING CHANGES ===")
        print(f"{'Idea':6} | {'Change':10} | {'New ELO':8}")
        print(f"{'-'*6} | {'-'*10} | {'-'*8}")
        
        for idea, change in sorted(rating_changes.items(), key=lambda x: abs(x[1]), reverse=True):
            elo_ratings[idea] += change
            idea_idx = ideas.index(idea) + 1
            # Format with arrow indicating positive/negative change
            direction = "↑" if change > 0 else "↓" if change < 0 else "="
            print(f"{idea_idx:6} | {direction} {abs(change):+7.1f} | {elo_ratings[idea]:8.1f}")
    
    # Log all match results if scientia_dir is available
    if scientia_dir:
        print("\n=== LOGGING TOURNAMENT RESULTS ===")
        try:
            for idea in ideas:
                idx = ideas.index(idea) + 1
                
                # Create a detailed match log for this idea
                idea_matches = match_results.get(idea, [])
                
                if idea_matches:
                    matchup_log = f"Tournament Summary\n\n"
                    matchup_log += f"Final ELO Rating: {elo_ratings[idea]:.1f}\n\n"
                    matchup_log += f"Vector scores by criterion:\n"
                    
                    # Include the idea's score vector using global TOURNAMENT_CRITERIA constant
                    for criterion, score in zip(TOURNAMENT_CRITERIA, list(score_vectors[idea])):
                        matchup_log += f"{criterion:25}: {score:.1f}\n"
                            
                    matchup_log += f"\nMatchup Results ({len(idea_matches)} matches):\n"
                    for match in idea_matches:
                        opp_idx = ideas.index(match['opponent']) + 1
                        matchup_log += f"\nVs. Idea {opp_idx} (ELO: {elo_ratings[match['opponent']]:.1f})\n"
                        matchup_log += f"Result: {'Won' if match['score'] > 0.5 else 'Lost' if match['score'] < 0.5 else 'Tied'}\n"
                        matchup_log += f"Score: {match['score']:.3f}\n"
                    
                    # Try to find metadata for this idea
                    idea_unique_id = None
                    idea_metadata = None
                    try:
                        # Look through all ideas to find the matching one
                        for id, text in idea_tracker.get_all_ideas().items():
                            if text == idea:
                                idea_metadata = idea_tracker.get_metadata(id)
                                idea_unique_id = idea_metadata.unique_id
                                break
                    except:
                        pass  # If we can't find metadata, continue anyway
                    
                    log_idea(scientia_dir, idx, matchup_log, "Tournament Results", 
                             elo_score=elo_ratings[idea], unique_id=idea_unique_id, metadata=idea_metadata)
                
        except Exception as e:
            print(f"Warning: Failed to log tournament results: {e}")
            traceback.print_exc()
    
    # Return the sorted list of ideas by their final ELO rating
    return sorted(
        [(idea, rating) for idea, rating in elo_ratings.items()],
        key=lambda x: x[1],
        reverse=True
    )

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
    if args.debug:
        DEBUG_MODE = True
        print("Debug logging enabled")

    # Initialize both clients with the selected models
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
    run_co_scientist_workflow(
        research_goal=user_research_goal,
        num_initial_ideas=args.initial_ideas,
        max_new_ideas_per_round=args.new_per_round,
        min_ideas=min_ideas,
        max_ideas=max_ideas,
        num_final_ideas=args.final_ideas,
        output_dir=args.output_dir
    )

# Example usage:
# 1. Specify research goal directly:
#    python scientia_v8.py --goal How can quantum computing improve machine learning?
#
# 2. Load research goal from a file:
#    python scientia_v8.py --goal-file research_questions.txt
#
# 3. Customize parameters:
#    python scientia_v8.py --goal-file research_questions.txt -i 30 -f 10 --debug
