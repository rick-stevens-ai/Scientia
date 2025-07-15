"""
Idea parser module for the Scientia system.

This module contains functions for parsing and formatting ideas, including
extraction of structured sections and formatting ideas for display.
"""

import re
from typing import List, Dict, Any, Optional

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
    
    # Look for standard section headers
    title_pattern = r'(?:\*\*)?Title(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Key Idea(?:\*\*)?:?|$)'
    key_idea_pattern = r'(?:\*\*)?Key Idea(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Paragraph(?:\*\*)?:?|$)'
    paragraph_pattern = r'(?:\*\*)?Paragraph(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Approach(?:\*\*)?:?|$)'
    approach_pattern = r'(?:\*\*)?Approach(?:\*\*)?:?\s*(.*?)(?=(?:\*\*)?Key References(?:\*\*)?:?|$)'
    references_pattern = r'(?:\*\*)?Key References(?:\*\*)?:?\s*(.*?)$'
    
    # Extract each section
    title_match = re.search(title_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    key_idea_match = re.search(key_idea_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    paragraph_match = re.search(paragraph_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    approach_match = re.search(approach_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    references_match = re.search(references_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    
    # Try alternative headers if standard ones aren't found
    if not title_match:
        title_match = re.search(r'(?:\*\*)?(?:Title|Heading|Name|Topic)(?:\*\*)?:?\s*(.*?)(?=\n|$)', 
                              idea_text, re.IGNORECASE | re.DOTALL)
    
    if not key_idea_match:
        key_idea_match = re.search(r'(?:\*\*)?(?:Key Idea|Hypothesis|Core Idea|Main Idea)(?:\*\*)?:?\s*(.*?)(?=\n|$)', 
                                 idea_text, re.IGNORECASE | re.DOTALL)
    
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
    
    # If no structured sections found, use whole text as key_idea
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
    Extract individual numbered ideas from a text output.
    
    Args:
        text: Text containing numbered ideas
        expected_count: Expected number of ideas to extract
        
    Returns:
        List of extracted ideas as strings
    """
    ideas = []
    
    # Try to match "Research Idea N:" format
    research_pattern = r'(?:\n|^)\s*(?:\*\*)?Research Idea (\d+)(?:\*\*)?:?\s*(.*?)(?=(?:\n|^)\s*(?:\*\*)?Research Idea \d+(?:\*\*)?:?|\Z)'
    research_matches = list(re.finditer(research_pattern, text, re.DOTALL | re.IGNORECASE))
    
    if research_matches:
        for match in research_matches:
            idea_text = match.group(2).strip()
            if idea_text:
                sections = parse_structured_idea(idea_text)
                ideas.append(format_structured_idea(sections))
    
    # If no research ideas found, try standard numbered list
    if not ideas:
        idea_pattern = r'(?:\n|^)\s*(\d+)\.\s+(.*?)(?=\n\s*\d+\.\s+|\Z)'
        matches = list(re.finditer(idea_pattern, text, re.DOTALL))
        
        if matches:
            for match in matches:
                idea_text = match.group(2).strip()
                if idea_text:
                    sections = parse_structured_idea(idea_text)
                    ideas.append(format_structured_idea(sections))
    
    # If still no ideas found, try to split by headers
    if not ideas:
        sections = re.split(r'\n\s*\n', text)
        for section in sections:
            if section.strip():
                sections = parse_structured_idea(section)
                ideas.append(format_structured_idea(sections))
    
    # Verify and adjust idea count
    if len(ideas) > expected_count:
        print(f"Found {len(ideas)} ideas, trimming to {expected_count}")
        ideas = ideas[:expected_count]
    elif len(ideas) < expected_count:
        print(f"Warning: Found only {len(ideas)} ideas, expected {expected_count}")
        # Add placeholder ideas if needed
        while len(ideas) < expected_count:
            placeholder = {
                "title": f"Placeholder Idea {len(ideas)+1}",
                "key_idea": "Please review generation output manually."
            }
            ideas.append(format_structured_idea(placeholder))
    
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
    # Look for lines that start with a number and indicate ranking
    rank_pattern = r'(?:\n|^)\s*(?:rank\s*#?\s*)?(\d+)[\.:\)]\s*(.*?)(?=\n\s*(?:rank\s*#?\s*)?\d+[\.:\)]|\Z)'
    matches = re.finditer(rank_pattern, ranking_output, re.DOTALL | re.IGNORECASE)
    
    # Create mapping from original ideas to their new positions
    ranking_map = {}
    for match in matches:
        rank = int(match.group(1))
        description = match.group(2).strip()
        
        # Try to match description with ideas
        for i, idea in enumerate(ideas):
            idea_sections = parse_structured_idea(idea)
            key_parts = [
                idea_sections.get("title", ""),
                idea_sections.get("key_idea", "")
            ]
            
            # Check if description contains enough of the idea to identify it
            for part in key_parts:
                if part and part.lower() in description.lower():
                    ranking_map[i] = rank - 1  # Convert to 0-based index
                    break
    
    # If couldn't match ideas to rankings, return original order
    if not ranking_map:
        return ideas
    
    # Create reordered list
    reordered = [None] * len(ideas)
    used_positions = set()
    
    # Place ideas in their ranked positions
    for orig_idx, new_idx in ranking_map.items():
        if new_idx < len(ideas) and new_idx not in used_positions:
            reordered[new_idx] = ideas[orig_idx]
            used_positions.add(new_idx)
    
    # Fill any gaps with unranked ideas
    unranked = [idea for i, idea in enumerate(ideas) if i not in ranking_map]
    for i in range(len(reordered)):
        if reordered[i] is None and unranked:
            reordered[i] = unranked.pop(0)
    
    # Verify no ideas were lost
    if None in reordered or len(reordered) != len(ideas):
        print("Warning: Error in reordering. Reverting to original order.")
        return ideas
    
    return reordered


def extract_citations(text: str) -> List[str]:
    """
    Extract citations in [Author Year] format from text.
    
    Args:
        text: Text to extract citations from
        
    Returns:
        List of unique citations found in the text
    """
    citation_pattern = r'\[(.*?\s+\d{4}(?:;\s*.*?\s+\d{4})*)\]'
    citations = re.findall(citation_pattern, text)
    unique_citations = set()
    
    for citation_group in citations:
        for single_citation in re.split(r';\s*', citation_group):
            unique_citations.add(single_citation.strip())
    
    return sorted(list(unique_citations))


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
    # Parse both ideas
    original_sections = parse_structured_idea(original_idea)
    refined_sections = parse_structured_idea(refined_idea)
    
    # Check key_idea changes
    original_key = original_sections.get("key_idea", "").lower()
    refined_key = refined_sections.get("key_idea", "").lower()
    
    if original_key and refined_key and len(original_key) > 10 and len(refined_key) > 10:
        original_words = set(original_key.split())
        refined_words = set(refined_key.split())
        
        if len(original_words) == 0:
            return True
        
        common_words = original_words.intersection(refined_words)
        similarity = len(common_words) / len(original_words)
        
        if similarity < threshold:
            return True
    
    # Check approach changes
    original_approach = original_sections.get("approach", "").lower()
    refined_approach = refined_sections.get("approach", "").lower()
    
    if original_approach and refined_approach and len(original_approach) > 20 and len(refined_approach) > 20:
        original_words = set(original_approach.split())
        refined_words = set(refined_approach.split())
        
        if len(original_words) == 0:
            return True
        
        common_words = original_words.intersection(refined_words)
        similarity = len(common_words) / len(original_words)
        
        if similarity < threshold:
            return True
    
    return False
