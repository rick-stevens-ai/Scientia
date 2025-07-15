"""
Idea parser module for the Scientia system.

This module contains functions for parsing, formatting, and manipulating
idea text and structured idea data.
"""

import re
import traceback
from typing import List, Dict, Any, Tuple, Optional, Set, Union


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
    """
    Extract citations in [Author Year] format from text.
    
    Args:
        text: Text containing citations
        
    Returns:
        List of extracted citations
    """
    citation_pattern = r'\[(.*?\s+\d{4}(?:;\s*.*?\s+\d{4})*)\]'
    citations = re.findall(citation_pattern, text)
    unique_citations = set()
    for citation_group in citations:
        for single_citation in re.split(r';\s*', citation_group):
            unique_citations.add(single_citation.strip())
    return sorted(list(unique_citations))


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
        print(f"Error parsing idea order from ranking: {e}")
        traceback.print_exc()
        return ideas
                    

