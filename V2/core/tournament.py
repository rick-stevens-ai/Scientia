"""
Tournament module for evaluating and comparing ideas in the Scientia system.

This module contains functions for conducting tournament-style evaluations
of ideas, computing score vectors, calculating ELO ratings, and managing
the competition between ideas.
"""

import random
import re
import textwrap
from typing import List, Dict, Tuple, Optional, Set, Any, Union

# Import from core modules
from .models import IdeaScore, IdeaEvolution, TOURNAMENT_CRITERIA
from .agents import call_agent, log_debug


def calculate_vector_score(scores_a: IdeaScore, scores_b: IdeaScore) -> float:
    '''
    Calculate a normalized score between two ideas based on their vector scores.
    Returns a value between 0 and 1 representing idea_a's performance vs idea_b.
    
    Args:
        scores_a: Vector of scores for idea A
        scores_b: Vector of scores for idea B
        
    Returns:
        Float between 0 and 1 representing idea_a's performance relative to idea_b
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
    
    Args:
        rating_a: Current ELO rating of idea A
        rating_b: Current ELO rating of idea B
        score: Value between 0 and 1 representing idea_a's performance against idea_b
        k: K-factor determining the maximum change in rating (default: 64.0)
        
    Returns:
        Tuple of (new_rating_a, new_rating_b)
    '''
    expected_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
    update = k * (score - expected_a)
    return rating_a + update, rating_b - update


def compute_idea_score_vectors(ideas: List[str], tournament_agent_prompt: str) -> Dict[str, IdeaScore]:
    """
    Compute score vectors for ideas in a single batch of calls to reduce API usage.
    
    Args:
        ideas: List of ideas to score
        tournament_agent_prompt: Prompt for the tournament agent
        
    Returns:
        Dictionary mapping idea text to its IdeaScore vector
    """
    score_vectors: Dict[str, IdeaScore] = {}
    
    print("\n=== COMPUTING SCORE VECTORS FOR IDEAS ===")
    print(f"This may take some time for {len(ideas)} ideas...")
    
    # Process ideas in batches of 5 to avoid overloading the API
    batch_size = 5
    for i in range(0, len(ideas), batch_size):
        batch = ideas[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(ideas) + batch_size - 1)//batch_size}...")
        
        # Format tournament criteria for more accurate scoring
        criteria_list = "\n".join([f"{i+1}. {criterion}: Scores should reflect how well the idea meets this criterion in relation to the research goal" 
                                 for i, criterion in enumerate(TOURNAMENT_CRITERIA)])
        
        # Create a prompt that requests scores for all ideas in the batch
        batch_prompt = (
            "Score each of the following ideas across all twenty scientific and technical criteria (1-10).\n\n"
            "SCORING CRITERIA:\n" + criteria_list + "\n\n"
            "IMPORTANT: Ensure your scoring is specific to the research goal and uses the full 1-10 range.\n\n" +
            "\n---\n".join(f"IDEA {j+1}:\n{idea}" for j, idea in enumerate(batch)) +
            "\n\nFor each idea, provide scores in this format:\n" +
            "IDEA N:\n" +
            "1. Plausibility = X\n" +
            "2. Theoretical Elegance = X\n" +
            "... (continue through all 20 criteria)\n"
        )
        
        # Get scores from tournament agent
        result = call_agent(
            tournament_agent_prompt,
            user_prompt=batch_prompt,
            agent_name="tournament"
        )
        
        # Parse scores for each idea in the batch
        for j, idea in enumerate(batch):
            # Look for the section about this idea
            idea_pattern = fr'(?i)IDEA\s*{j+1}:|SCORES?\s*FOR\s*IDEA\s*{j+1}:'
            idea_match = re.search(idea_pattern, result)
            if idea_match:
                # Extract scores from this section until the next idea or end
                section_end = result.find(f"IDEA {j+2}:") if j < len(batch)-1 else len(result)
                section = result[idea_match.start():section_end]
                
                # Extract individual scores - flexible pattern to match criteria
                scores = []
                
                # Match any score format with number or named criterion
                score_pattern = r'(?i)(?:\d+\.\s*(?:[^=]+)|(?:' + '|'.join(TOURNAMENT_CRITERIA) + r'))[^=]*=\s*(\d+(?:\.\d+)?)'
                score_matches = re.finditer(score_pattern, section)
                
                for match in score_matches:
                    try:
                        score = float(match.group(1))
                        if 1 <= score <= 10:
                            scores.append(score)
                    except ValueError:
                        continue
                
                # If we found exactly the right number of scores, create the score vector
                if len(scores) == len(TOURNAMENT_CRITERIA):
                    score_vectors[idea] = IdeaScore(*scores)
                else:
                    print(f"Warning: Found {len(scores)} scores for idea {j+1}, expected {len(TOURNAMENT_CRITERIA)}")
                    # Use default scores as fallback
                    score_vectors[idea] = IdeaScore(*([6.0] * len(TOURNAMENT_CRITERIA)))
    
    print(f"Computed score vectors for {len(score_vectors)} ideas")
    return score_vectors


def get_criteria_scores_for_idea(idea_text: str, idea_tracker: IdeaEvolution) -> Dict[str, float]:
    """
    Find stored criteria scores for an idea from the tracker.
    
    Args:
        idea_text: The text of the idea to find scores for
        idea_tracker: The IdeaEvolution instance containing idea metadata
        
    Returns:
        Dictionary mapping criteria to scores, or empty dict if not found
    """
    # Look for the idea in the tracker
    for idea_id, text in idea_tracker.get_all_ideas().items():
        if text == idea_text:
            # Found the idea, get its metadata
            metadata = idea_tracker.get_metadata(idea_id)
            if hasattr(metadata, 'criteria_scores') and metadata.criteria_scores:
                return metadata.criteria_scores
    
    # If not found or no scores, return empty dict
    return {}


def is_valid_idea(idea: str) -> bool:
    """
    Check if an idea is valid and complete for tournament comparison.
    
    Args:
        idea: The idea text to validate
        
    Returns:
        True if the idea is valid, False otherwise
    """
    # Basic length check - very minimal to allow most reasonable ideas
    if not idea or len(idea.strip()) < 20:
        return False
        
    # More flexible validation - accept ideas if they have any meaningful content
    # Either have a key_idea or the idea text itself is substantial
    if "**Key Idea**" in idea or (len(idea) > 100 and "**" in idea):
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


def run_optimized_tournament(
    ideas: List[str],
    tournament_agent_prompt: str,
    num_opponents: int = 10,
    scientia_dir: Optional[str] = None,
    only_update_ideas: Optional[List[str]] = None,
    idea_tracker: Optional[IdeaEvolution] = None
) -> List[Tuple[str, float]]:
    """
    Run an optimized tournament using pre-computed score vectors and batched ELO updates.
    
    Args:
        ideas: List of ideas to compare
        tournament_agent_prompt: Prompt for the tournament agent
        num_opponents: Number of random opponents for each idea
        scientia_dir: Optional directory for logging
        only_update_ideas: Optional list of ideas to compute score vectors for
        idea_tracker: Optional IdeaEvolution instance for accessing criteria scores
        
    Returns:
        List of (idea, final_elo_rating) tuples sorted by rating
    """
    # Filter out incomplete or invalid ideas first
    valid_ideas = []
    for i, idea in enumerate(ideas):
        if is_valid_idea(idea):
            valid_ideas.append(idea)
        else:
            print(f"WARNING: Idea {i+1} is incomplete or invalid and will be excluded from the tournament.")
            print(f"Preview: {idea[:100]}...")
            
    if len(valid_ideas) < 2:
        print("ERROR: Not enough valid ideas for tournament. Need at least 2.")
        # Return all ideas with default ratings
        return [(idea, 1500.0) for idea in ideas]
        
    # Use valid ideas for the tournament
    ideas = valid_ideas
    
    # Initialize or get the global idea_score_vectors dictionary
    # This is retained across calls to allow reuse of score vectors
    global idea_score_vectors
    if 'idea_score_vectors' not in globals():
        idea_score_vectors = {}
    
    # Determine if we should use stored criteria scores
    use_criteria_scores = idea_tracker is not None
    if use_criteria_scores:
        print("Using stored criteria scores from idea tracking system")
    
    # Determine which ideas need score vector computation
    ideas_to_score = []
    if only_update_ideas is not None:
        # Only compute vectors for specified ideas (those improved this round)
        ideas_to_score = only_update_ideas
        print(f"Only updating score vectors for {len(ideas_to_score)} improved ideas")
    else:
        # If using criteria scores, we need to convert all ideas' stored scores
        if use_criteria_scores:
            ideas_to_score = []  # No need to compute scores, we'll use stored ones
            print("Using stored criteria scores for all ideas")
        else:
            # First time or full tournament - compute all via tournament agent
            ideas_to_score = ideas
            print(f"Computing score vectors for all {len(ideas_to_score)} ideas")
    
    # If using stored criteria scores, convert them to IdeaScore objects
    if use_criteria_scores:
        for idea in ideas:
            criteria_scores = get_criteria_scores_for_idea(idea, idea_tracker)
            if criteria_scores:
                # Convert dictionary to ordered scores matching TOURNAMENT_CRITERIA
                try:
                    score_values = [criteria_scores.get(criterion, 6.0) for criterion in TOURNAMENT_CRITERIA]
                    idea_score_vectors[idea] = IdeaScore(*score_values)
                    log_debug(f"Using stored criteria scores for idea starting with: {idea[:50]}...")
                except Exception as e:
                    print(f"Error converting criteria scores: {e}")
                    # Fall back to computing scores if conversion fails
                    if idea not in ideas_to_score:
                        ideas_to_score.append(idea)
            else:
                # No stored scores, need to compute
                if idea not in ideas_to_score:
                    ideas_to_score.append(idea)
    
    # Compute new score vectors only for ideas that need them
    if ideas_to_score:
        print(f"Computing score vectors for {len(ideas_to_score)} ideas that need updating")
        new_score_vectors = compute_idea_score_vectors(ideas_to_score, tournament_agent_prompt)
        
        # Update global score vector dictionary
        for idea, vector in new_score_vectors.items():
            idea_score_vectors[idea] = vector
            
            # Also update criteria scores in idea metadata if possible
            if idea_tracker:
                for idea_id, text in idea_tracker.get_all_ideas().items():
                    if text == idea:
                        # Convert vector to dictionary for storage
                        criteria_dict = {
                            criterion: score 
                            for criterion, score in zip(TOURNAMENT_CRITERIA, list(vector))
                        }
                        idea_tracker.update_criteria_scores(idea_id, criteria_dict)
                        break
        
    # Ensure all ideas have score vectors
    for idea in ideas:
        if idea not in idea_score_vectors:
            print(f"Warning: Missing score vector for an idea. Generating default.")
            # Generate default score vector (should only happen in edge cases)
            idea_score_vectors[idea] = IdeaScore(*([6.0] * len(TOURNAMENT_CRITERIA)))
            
    # Use the updated global score vectors
    score_vectors = {idea: idea_score_vectors[idea] for idea in ideas}
    
    # Initialize ELO ratings
    elo_ratings = {idea: 1200.0 for idea in ideas}
    
    print("\n=== RUNNING TOURNAMENT WITH PRE-COMPUTED SCORES ===")
    
    # For each idea, select random opponents
    pending_elo_updates: List[Tuple[str, str, float]] = []  # (idea_a, idea_b, score)
    match_results: Dict[str, List[Dict[str, Any]]] = {}  # Track match results for each idea
    
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
            from .file_utils import log_idea
            
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
            import traceback
            traceback.print_exc()
    
    # Return the sorted list of ideas by their final ELO rating
    return sorted(
        [(idea, rating) for idea, rating in elo_ratings.items()],
        key=lambda x: x[1],
        reverse=True
    )


# Helper functions for parsing
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

