"""
Evaluation module for the Scientia system.

This module contains functions for evaluating ideas, including idea criteria
scoring, tournament evaluation, and result analysis.
"""

import os
import re
from typing import List, Dict, Tuple, Optional, Any

# Import from other core modules
from .models import TOURNAMENT_CRITERIA
from .agents import call_agent


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
    
    # Format criteria list for the prompt
    criteria_list = "\n".join([f"{i+1}. {criterion}: {description}" 
                            for i, (criterion, description) in enumerate(zip(
                                TOURNAMENT_CRITERIA, 
                                [
                                    "Scientific plausibility",
                                    "Simplicity, parsimony, and mathematical beauty",
                                    "Formal mathematical foundation",
                                    "Derivation from fundamental principles",
                                    "Mathematical/physical symmetries and invariants",
                                    "Information-theoretic aspects and entropy",
                                    "Ability to make testable predictions",
                                    "Applicability across multiple domains",
                                    "Uniqueness of the theoretical approach",
                                    "Strength of underlying theoretical basis",
                                    "Emergent behaviors and complexity",
                                    "Theoretical energy requirements",
                                    "Physical conservation principles",
                                    "Mathematical/physical scaling relations",
                                    "Quantum mechanical considerations",
                                    "Algorithmic and computational aspects",
                                    "Statistical and ensemble properties",
                                    "Spatial/temporal geometric properties",
                                    "Critical phenomena and transitions",
                                    "Stability and equilibrium properties"
                                ]
                            ))])
    
    # Create the evaluation prompt
    evaluation_prompt = (
        f"Evaluate the following research idea against {len(TOURNAMENT_CRITERIA)} scientific criteria "
        f"in relation to this research goal:\n\n"
        f"RESEARCH GOAL: {research_goal}\n\n"
        f"IDEA TO EVALUATE:\n{idea_text}\n\n"
        f"EVALUATION CRITERIA:\n{criteria_list}\n\n"
        f"For each criterion, provide:\n"
        f"1. A score from 1-10 (where 1 is extremely poor and 10 is outstanding)\n"
        f"2. A brief explanation of your scoring rationale\n"
        f"3. Concrete suggestions for improvement\n\n"
        f"Format your response with each criterion as a separate section. For each section, include the score "
        f"in the format 'Score: X/10' followed by your explanation and suggestions."
    )
    
    # Call the tournament agent to evaluate the idea
    evaluation_result = call_agent(
        tournament_agent_prompt,
        user_prompt=evaluation_prompt,
        agent_name="tournament"
    )
    
    # Parse the scores from the result
    scores = {}
    for i, criterion in enumerate(TOURNAMENT_CRITERIA):
        score_pattern = rf'(?i){i+1}\.\s*{re.escape(criterion)}.*?Score:\s*(\d+(?:\.\d+)?)/10'
        score_match = re.search(score_pattern, evaluation_result, re.DOTALL)
        if not score_match:
            # Try a more flexible pattern
            score_pattern = rf'(?i){criterion}.*?(?:Score|Rating):\s*(\d+(?:\.\d+)?)'
            score_match = re.search(score_pattern, evaluation_result, re.DOTALL)
        
        if score_match:
            try:
                score = float(score_match.group(1))
                scores[criterion] = score
            except ValueError:
                scores[criterion] = 5.0  # Default score if parsing fails
        else:
            scores[criterion] = 5.0  # Default score if pattern not found
    
    # Return scores and the full evaluation text
    return scores, evaluation_result


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
        if idea_text:
            # Extract key phrases from the idea text
            from .idea_parser import parse_structured_idea
            idea_sections = parse_structured_idea(idea_text)
            title = idea_sections.get("title", "").lower()
            key_idea = idea_sections.get("key_idea", "").lower()
            
            # Create a set of keywords from the title and key idea
            keywords = set()
            if title:
                keywords.update(title.split()[:5])  # First 5 words of title
            if key_idea:
                keywords.update(key_idea.split()[:10])  # First 10 words of key idea
            
            # Remove common words
            common_words = {"the", "a", "an", "and", "or", "in", "on", "of", "to", "for", "with", "is", "are", "that", "this"}
            keywords = keywords - common_words
            
            if keywords:
                # Look for sections that contain multiple keywords
                sections = re.split(r'\n(?:##+ |[A-Z][a-z]+:)', feedback_text)
                for section in sections:
                    section_lower = section.lower()
                    matches = [keyword for keyword in keywords if keyword in section_lower]
                    if len(matches) >= 2 and len(section) > 100:  # At least 2 keyword matches and reasonable length
                        return section.strip()
        
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
        import traceback
        traceback.print_exc()
        return feedback_text  # If extraction fails, return the full text as a fallback


def generate_final_report(scientia_dir: str, idea_num: int, idea_text: str, 
                         final_elo: float, log_file_path: str, idea_tracker: Optional[Any] = None) -> bool:
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
        from .file_utils import write_file
        from .idea_parser import parse_structured_idea, extract_citations
        
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
        import traceback
        traceback.print_exc()
        return False

