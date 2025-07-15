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

from .models import IdeaScore, IdeaEvolution, TOURNAMENT_CRITERIA
from .agents import call_agent, get_tournament_agent_prompt


def calculate_vector_score(scores_a: IdeaScore, scores_b: IdeaScore) -> float:
    """
    Calculate a normalized score between two ideas based on their vector scores.
    Returns a value between 0 and 1 representing idea_a's performance vs idea_b.
    
    Args:
        scores_a: Vector of scores for idea A
        scores_b: Vector of scores for idea B
        
    Returns:
        Float between 0 and 1 representing idea_a's performance relative to idea_b
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


def calculate_elo_update(rating_a: float, rating_b: float, score: float, k: float = 64.0) -> Tuple[float, float]:
    """
    Calculate updated ELO ratings based on the comparison score.
    
    Args:
        rating_a: Current ELO rating of idea A
        rating_b: Current ELO rating of idea B
        score: Value between 0 and 1 representing idea_a's performance against idea_b
        k: K-factor determining the maximum change in rating (default: 64.0)
        
    Returns:
        Tuple of (new_rating_a, new_rating_b)
    """
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
        
        # Format tournament criteria for accurate scoring
        criteria_list = "\n".join([f"{i+1}. {criterion}: Scores should reflect how well the idea meets this criterion" 
                                 for i, criterion in enumerate(TOURNAMENT_CRITERIA)])
        
        # Create a prompt that requests scores for all ideas in the batch
        batch_prompt = (
            "Score each of the following ideas across all twenty scientific and technical criteria (1-10).\n\n"
            "SCORING CRITERIA:\n" + criteria_list + "\n\n"
            "IMPORTANT: Use the full 1-10 range.\n\n" +
            "\n---\n".join(f"IDEA {j+1}:\n{idea}" for j, idea in enumerate(batch)) +
            "\n\nFor each idea, provide scores in this format:\n" +
            "IDEA N:\n" +
            "1. Criterion = X\n" +
            "2. Criterion = X\n" +
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
                # Extract scores until the next idea or end
                section_end = result.find(f"IDEA {j+2}:") if j < len(batch)-1 else len(result)
                section = result[idea_match.start():section_end]
                
                # Extract individual scores
                scores = []
                score_pattern = r'(?i)(?:\d+\.\s*(?:[^=]+)|(?:' + '|'.join(TOURNAMENT_CRITERIA) + r'))[^=]*=\s*(\d+(?:\.\d+)?)'
                score_matches = re.finditer(score_pattern, section)
                
                for match in score_matches:
                    try:
                        score = float(match.group(1))
                        if 1 <= score <= 10:
                            scores.append(score)
                    except ValueError:
                        continue
                
                # Create score vector if we found the right number of scores
                if len(scores) == len(TOURNAMENT_CRITERIA):
                    score_vectors[idea] = IdeaScore(*scores)
                else:
                    print(f"Warning: Found {len(scores)} scores for idea {j+1}, expected {len(TOURNAMENT_CRITERIA)}")
                    score_vectors[idea] = IdeaScore(*([6.0] * len(TOURNAMENT_CRITERIA)))
    
    print(f"Computed score vectors for {len(score_vectors)} ideas")
    return score_vectors


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
    # Initialize ELO ratings and score vectors
    elo_ratings = {idea: 1200.0 for idea in ideas}
    
    # Global storage for score vectors
    global idea_score_vectors
    if 'idea_score_vectors' not in globals():
        idea_score_vectors = {}
    
    # Determine which ideas need score computation
    ideas_to_score = only_update_ideas if only_update_ideas is not None else ideas
    
    # Compute new score vectors only for ideas that need them
    if ideas_to_score:
        print(f"Computing score vectors for {len(ideas_to_score)} ideas...")
        new_score_vectors = compute_idea_score_vectors(ideas_to_score, tournament_agent_prompt)
        
        # Update global score vector dictionary
        for idea, vector in new_score_vectors.items():
            idea_score_vectors[idea] = vector
    
    # Ensure all ideas have score vectors
    for idea in ideas:
        if idea not in idea_score_vectors:
            print(f"Warning: Missing score vector for an idea. Using default.")
            idea_score_vectors[idea] = IdeaScore(*([6.0] * len(TOURNAMENT_CRITERIA)))
    
    # Run tournament matches
    pending_elo_updates: List[Tuple[str, str, float]] = []
    match_results: Dict[str, List[Dict[str, Any]]] = {}
    
    for i, idea_a in enumerate(ideas):
        print(f"\nIdea {i+1}/{len(ideas)}: Tournament Matchups")
        match_results[idea_a] = []
        
        # Get random opponents (excluding self)
        possible_opponents = ideas[:i] + ideas[i+1:]
        opponents = random.sample(possible_opponents, min(num_opponents, len(possible_opponents)))
        
        for match_num, idea_b in enumerate(opponents, 1):
            # Calculate vector-based score
            match_score = calculate_vector_score(idea_score_vectors[idea_a], idea_score_vectors[idea_b])
            
            # Queue the ELO update
            pending_elo_updates.append((idea_a, idea_b, match_score))
            
            # Store match result for logging
            match_results[idea_a].append({
                'opponent': idea_b,
                'score': match_score,
                'vector_a': idea_score_vectors[idea_a],
                'vector_b': idea_score_vectors[idea_b]
            })
    
    # Process all ELO updates in batches
    print("\n=== PROCESSING BATCHED ELO UPDATES ===")
    batch_size = 50
    
    for i in range(0, len(pending_elo_updates), batch_size):
        batch = pending_elo_updates[i:i+batch_size]
        
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
        for idea, change in rating_changes.items():
            elo_ratings[idea] += change
    
    # Return sorted list of ideas by final ELO rating
    return sorted(
        [(idea, rating) for idea, rating in elo_ratings.items()],
        key=lambda x: x[1],
        reverse=True
    )
