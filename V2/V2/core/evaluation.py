"""
Evaluation module for the Scientia system.

This module contains functions for evaluating ideas, including idea criteria
scoring, tournament evaluation, and result analysis.
"""

import os
import re
from typing import List, Dict, Tuple, Optional, Any

from .models import TOURNAMENT_CRITERIA
from .agents import call_agent, get_tournament_agent_prompt
from .idea_parser import parse_structured_idea, extract_citations
from .file_utils import write_file


def evaluate_idea_with_criteria(idea_text: str, research_goal: str, tournament_agent_prompt: str) -> Tuple[Dict[str, float], str]:
    """
    Evaluate a single idea against the scientific criteria.
    
    Args:
        idea_text: The text content of the idea
        research_goal: The research goal or question
        tournament_agent_prompt: The prompt for the tournament agent
        
    Returns:
        Tuple of (criteria_scores, full_evaluation_text)
    """
    print(f"Evaluating idea against scientific criteria...")
    evaluation_prompt = (
        f"Evaluate the following research idea against {len(TOURNAMENT_CRITERIA)} scientific criteria "
        f"in relation to this research goal:\n\n"
        f"RESEARCH GOAL: {research_goal}\n\n"
        f"IDEA TO EVALUATE:\n{idea_text}\n\n"
        f"For each criterion, provide:\n"
        f"1. A score from 1-10 (where 1 is extremely poor and 10 is outstanding)\n"
        f"2. A brief explanation of your scoring rationale\n"
        f"3. Concrete suggestions for improvement\n\n"
        f"Format your response with each criterion as a separate section."
    )
    
    evaluation_result = call_agent(
        tournament_agent_prompt,
        user_prompt=evaluation_prompt,
        agent_name="tournament"
    )
    
    # Parse the scores from the result
    scores = {}
    for criterion in TOURNAMENT_CRITERIA:
        score_pattern = rf'(?i){re.escape(criterion)}.*?(?:Score|Rating):\s*(\d+(?:\.\d+)?)'
        score_match = re.search(score_pattern, evaluation_result, re.DOTALL)
        
        if score_match:
            try:
                score = float(score_match.group(1))
                scores[criterion] = score
            except ValueError:
                scores[criterion] = 5.0  # Default score if parsing fails
        else:
            scores[criterion] = 5.0  # Default score if pattern not found
    
    return scores, evaluation_result


def extract_idea_specific_feedback(feedback_text: str, idea_num: int, total_ideas: int, idea_text: str = "") -> str:
    """
    Extract feedback specific to a single idea from comprehensive feedback text.
    
    Args:
        feedback_text: The complete feedback text for all ideas
        idea_num: The idea number to extract feedback for (1-based)
        total_ideas: Total number of ideas in the feedback
        idea_text: Optional text of the idea to help match content
        
    Returns:
        Extracted feedback specific to the requested idea
    """
    try:
        # Look for specific section headers about this idea
        idea_patterns = [
            fr'(?i)(?:^|\n)(?:##+ *)?{idea_num}\. +(?:[^#\n]+)(?:\n|$).*?(?=(?:^|\n)(?:##+ *)?(?:{idea_num+1}|[^{idea_num}])\. +|\Z)',
            fr'(?i)(?:^|\n)(?:##+ *)?Idea *{idea_num}[:.] *(?:[^#\n]+)(?:\n|$).*?(?=(?:^|\n)(?:##+ *)?Idea *(?:{idea_num+1}|[^{idea_num}])[:.] *|\Z)'
        ]
        
        for pattern in idea_patterns:
            matches = re.finditer(pattern, feedback_text, re.DOTALL)
            for match in matches:
                extracted_text = match.group(0).strip()
                if len(extracted_text) > 50:  # Reasonable minimum length
                    return extracted_text
        
        # If no specific sections found, look for any mention of the idea
        mention_pattern = fr'(?i)(?:^|\n)(?:.*?Idea *{idea_num}.*?)(?:\n|$).*?(?=\n[A-Z#]|\Z)'
        matches = re.finditer(mention_pattern, feedback_text, re.DOTALL)
        for match in matches:
            extracted_text = match.group(0).strip()
            if len(extracted_text) > 50:
                return extracted_text
        
        # If still nothing found, return a note
        return f"Note: No specific feedback found for Idea {idea_num}"
        
    except Exception as e:
        print(f"Error extracting idea-specific feedback: {e}")
        return feedback_text  # Return full text as fallback


def generate_final_report(scientia_dir: str, idea_num: int, idea_text: str, 
                         final_elo: float, log_file_path: str, 
                         idea_tracker: Optional[Any] = None) -> bool:
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
        
        # Find idea's metadata and scores
        idea_metadata = None
        idea_unique_id = None
        criteria_scores = {}
        
        if idea_tracker:
            for id, text in idea_tracker.get_all_ideas().items():
                if text == idea_text:
                    idea_metadata = idea_tracker.get_metadata(id)
                    idea_unique_id = getattr(idea_metadata, "unique_id", None)
                    criteria_scores = getattr(idea_metadata, "criteria_scores", {}) or {}
                    break
        
        # Parse structured sections and citations
        citations = extract_citations(idea_text)
        sections = parse_structured_idea(idea_text)
        
        # Read evolution history
        evolution_history = []
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                log_content = f.read()
                entries = log_content.split("="*80)
                
                for entry in entries:
                    if entry.strip():
                        timestamp_match = re.search(r'TIMESTAMP: (.*?)$', entry, re.MULTILINE)
                        phase_match = re.search(r'PHASE: (.*?)(?:, ROUND:|$)', entry, re.MULTILINE)
                        round_match = re.search(r'ROUND: (\d+)', entry)
                        elo_match = re.search(r'ELO SCORE: (\d+\.\d+)', entry)
                        
                        if timestamp_match and phase_match:
                            evolution_history.append({
                                "timestamp": timestamp_match.group(1).strip(),
                                "phase": phase_match.group(1).strip(),
                                "round": int(round_match.group(1)) if round_match else None,
                                "elo_score": float(elo_match.group(1)) if elo_match else None,
                                "content": entry.split("\n\n", 1)[1] if "\n\n" in entry else ""
                            })
        
        # Generate report content
        report_content = f"""# Final Report: Idea {idea_num}

## Title
{sections.get("title", "Untitled")}

## One Sentence Summary
{sections.get("key_idea", "No summary available")}

## Final ELO Score
**Final ELO Score:** {final_elo:.1f}

## Scientific Criteria Ratings
"""
        
        # Add criteria scores
        if criteria_scores:
            report_content += "| Criterion | Score |\n|---|---:|\n"
            for criterion in TOURNAMENT_CRITERIA:
                score = criteria_scores.get(criterion, 0.0)
                report_content += f"| {criterion} | {score:.1f}/10 |\n"
        
        # Add evolution history
        report_content += "\n## Evolution History\n\n"
        for entry in evolution_history:
            round_info = f" (Round {entry['round']})" if entry['round'] is not None else ""
            report_content += f"### {entry['phase']}{round_info}\n"
            report_content += f"**Timestamp:** {entry['timestamp']}\n\n"
            if entry['elo_score'] is not None:
                report_content += f"**ELO Score:** {entry['elo_score']:.1f}\n\n"
            report_content += f"{entry['content'].strip()}\n\n"
            report_content += "---\n\n"
        
        # Write report to file
        return write_file(report_file, report_content)
        
    except Exception as e:
        print(f"Error generating final report for idea {idea_num}: {e}")
        import traceback
        traceback.print_exc()
        return False
