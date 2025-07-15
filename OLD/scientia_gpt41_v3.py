import sys
import time
import textwrap
import os
import re
import json
import datetime
import shutil
import traceback
import pickle
import hashlib
import signal
from pathlib import Path
from openai import OpenAI
from openai import APIError, APITimeoutError, APIConnectionError, RateLimitError
from typing import List, Dict, Any, Tuple, Optional, Union, Callable

# Initialize OpenAI client with API key and proper configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY environment variable not set")
    sys.exit(1)

MODEL_ID = "gpt-4.1-2025-04-14"  # Latest April 2025 release
MODEL_TIMEOUT = 60.0  # Timeout in seconds

client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=MODEL_TIMEOUT
)

# Debug and logging settings
DEBUG_MODE = True       # Enable detailed logging
CHECKPOINT_FREQ = True  # Enable state checkpointing
AUTO_BACKUP = True      # Enable automatic backups
MAX_BACKUPS = 3         # Maximum number of backup files to keep
RECOVERY_ENABLED = True # Enable automatic recovery from checkpoints
##############################################################################
# Directory Management and File Operations
##############################################################################

def log_debug(message: str) -> None:
    """
    Log debug messages if debug mode is enabled.
    
    Args:
        message: Debug message to log
    """
    if DEBUG_MODE:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DEBUG {timestamp}] {message}")

def generate_problem_name(research_goal: str, max_length: int = 30) -> str:
    """
    Generate a short, descriptive name for the research problem.
    
    Args:
        research_goal: The full research goal statement
        max_length: Maximum length of the generated name
        
    Returns:
        A directory-friendly name for the problem
    """
    log_debug(f"Generating problem name from: {research_goal}")
    cleaned_goal = re.sub(r'[^a-zA-Z0-9\s]', '', research_goal).strip()
    words = cleaned_goal.split()
    if not words:
        return "research_problem"
    name = "_".join(words[:5]).lower()[:max_length].rstrip('_')
    result = name if name else "research_problem"
    log_debug(f"Generated problem name: {result}")
    return result

def create_directory(dir_path: str) -> bool:
    """
    Create a directory with verification.
    
    Args:
        dir_path: Absolute path to the directory to create
        
    Returns:
        True if directory was created successfully, False otherwise
    """
    try:
        log_debug(f"Creating directory: {dir_path}")
        os.makedirs(dir_path, exist_ok=True)
        
        # Verify directory was created
        if not os.path.isdir(dir_path):
            print(f"Error: Failed to verify directory creation: {dir_path}")
            return False
            
        log_debug(f"Directory created and verified: {dir_path}")
        return True
    except Exception as e:
        print(f"Error creating directory {dir_path}: {e}")
        traceback.print_exc()
        return False

def write_file(file_path: str, content: str) -> bool:
    """
    Write content to a file with verification.
    
    Args:
        file_path: Absolute path to the file
        content: Content to write to the file
        
    Returns:
        True if file was written successfully, False otherwise
    """
    try:
        log_debug(f"Writing file: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Verify file was written
        if not os.path.exists(file_path):
            print(f"Error: Failed to verify file was written: {file_path}")
            return False
            
        log_debug(f"File written and verified: {file_path}")
        return True
    except Exception as e:
        print(f"Error writing file {file_path}: {e}")
        traceback.print_exc()
        return False

def append_file(file_path: str, content: str) -> bool:
    """
    Append content to a file with verification.
    
    Args:
        file_path: Absolute path to the file
        content: Content to append to the file
        
    Returns:
        True if file was updated successfully, False otherwise
    """
    try:
        log_debug(f"Appending to file: {file_path}")
        
        # Get file size before append for verification
        file_size_before = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        # Verify file was updated
        if not os.path.exists(file_path):
            print(f"Error: Failed to verify file exists after append: {file_path}")
            return False
            
        file_size_after = os.path.getsize(file_path)
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
             round_num: Optional[int] = None, elo_score: Optional[float] = None) -> bool:
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
        
    Returns:
        True if logging was successful, False otherwise
    """
    try:
        log_file = os.path.join(scientia_dir, f"idea_{idea_num}.log")
        
        # Prepare log entry with timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "phase": phase,
            "round": round_num,
            "elo_score": elo_score,
            "content": idea_text
        }
        
        # We no longer need individual JSON files since everything is in the per-idea log
        # Keep the state in memory for the current run but don't write separate JSON files
        
        # Append to existing log or create new file
        header = f"{'=' * 80}\n"
        header += f"TIMESTAMP: {timestamp}\n"
        header += f"PHASE: {phase}"
        if round_num is not None:
            header += f", ROUND: {round_num}"
        if elo_score is not None:
            header += f", ELO SCORE: {elo_score:.1f}"
        header += f"\n{'=' * 80}\n\n"
        entry = header + idea_text + "\n\n"
        
        if os.path.exists(log_file):
            return append_file(log_file, entry)
        else:
            return write_file(log_file, f"IDEA {idea_num} EVOLUTION LOG\n\n" + entry)
            
    except Exception as e:
        print(f"Error logging idea {idea_num}: {e}")
        traceback.print_exc()
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
        print(f"Error parsing ranking order: {e}")
        traceback.print_exc()
        return ideas
def generate_final_report(scientia_dir: str, idea_num: int, idea_text: str, 
                         final_elo: float, log_file_path: str) -> bool:
    """
    Generate a comprehensive final report for an idea in markdown format.
    
    Args:
        scientia_dir: Path to the .scientia directory
        idea_num: The idea's number/ID
        idea_text: The final version of the idea
        final_elo: The final ELO score
        log_file_path: Path to the idea's log file
        
    Returns:
        True if report was generated successfully, False otherwise
    """
    try:
        report_file = os.path.join(scientia_dir, f"idea_{idea_num}_final.md")
        
        # Extract citations from the idea text
        citations = extract_citations(idea_text)
        
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
                    
                    # Skip header entry (first entry might be just the header)
                    if timestamp_match and phase_match:
                        timestamp = timestamp_match.group(1).strip()
                        phase = phase_match.group(1).strip()
                        round_num = int(round_match.group(1)) if round_match else None
                        elo_score = float(elo_match.group(1)) if elo_match else None
                        
                        # Extract content after the metadata section
                        content_parts = entry.split("\n\n", 1)
                        content = content_parts[1] if len(content_parts) > 1 else ""
                        
                        evolution_history.append({
                            "timestamp": timestamp,
                            "phase": phase,
                            "round": round_num,
                            "elo_score": elo_score,
                            "content": content.strip()
                        })
        
        # Generate the report content
        report_content = f"""# Final Report: Idea {idea_num}

## Final ELO Score: {final_elo:.1f}

## Final Hypothesis

{idea_text}

## Comprehensive Analysis

This document provides a full analysis of the idea, including its evolution, strengths, weaknesses, and potential applications. Below we trace the development of this idea through each phase of the research process.

## Evolution History

The idea underwent several iterations during the research process:

"""
        
        # Extract key sections from the final idea
        sections = parse_structured_idea(idea_text)
        
        # Add a more detailed breakdown of the final idea
        report_content += "## Detailed Breakdown\n\n"
        
        if sections.get("title"):
            report_content += f"### Title\n\n{sections['title']}\n\n"
        
        if sections.get("key_idea"):
            report_content += f"### Key Idea\n\n{sections['key_idea']}\n\n"
        
        if sections.get("paragraph"):
            report_content += f"### Detailed Explanation\n\n{sections['paragraph']}\n\n"
        
        if sections.get("approach"):
            report_content += f"### Implementation Approach\n\n{sections['approach']}\n\n"
        
        if sections.get("references"):
            report_content += f"### Key References\n\n{sections['references']}\n\n"
        
        # Add evolution history with more detail
        report_content += "## Complete Evolution History\n\n"
        report_content += "This section documents the complete evolution of the idea through each phase of the research process.\n\n"
        
        for i, entry in enumerate(evolution_history):
            report_content += f"### {i+1}. {entry['phase']}"
            if entry['round'] is not None:
                report_content += f" (Round {entry['round']})"
            report_content += f"\n**Timestamp:** {entry['timestamp']}\n\n"
            
            if entry['elo_score'] is not None:
                report_content += f"**ELO Score:** {entry['elo_score']:.1f}\n\n"
            
            report_content += f"{entry['content']}\n\n"
            
            # Add analysis of changes if this isn't the first entry
            if i > 0 and i < len(evolution_history) - 1:
                # Placeholder for future change analysis
                pass
        
        # Add citations section
        if citations:
            report_content += "## Citations\n\n"
            for citation in citations:
                report_content += f"- {citation}\n"
        
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
        "1: Severely deficient\n"
        "2-3: Poor performance\n"
        "4-5: Below average\n"
        "6: Average\n" 
        "7-8: Above average\n"
        "9: Excellent\n"
        "10: Exceptional/groundbreaking\n\n"
        "IMPORTANT: If one idea is incomplete, fragmentary, or missing key components, "
        "assign it appropriately low scores (1-3) based on the available content. If both "
        "ideas have all five required components (Title, Key idea, Paragraph explanation, "
        "Approach, and Key references), compare them fairly across all criteria.\n\n"
        "REQUIRED FORMAT: You MUST provide exactly 8 scores for each idea using the format above, "
        "with no exceptions. After scoring, you may provide brief justifications for your scores.\n\n"
    )
# Helper function to call an agent via the OpenAI ChatCompletion API
##############################################################################

def call_agent(
    agent_system_prompt: str,
    user_prompt: str,
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

def run_co_scientist_workflow(
    research_goal: str,
    num_ideas: int = 20,
    num_rounds: int = 4
) -> None:
    """
    Modified workflow that keeps all ideas for four rounds, then runs a tournament:
    
    1. The Supervisor Agent sets up the initial tasks
    2. Each round:
       - Generation (or Evolution in subsequent rounds) Agent produces/refines ideas
       - Reflection Agent reviews and evaluates hypotheses
       - Proximity Check Agent ensures alignment/feasibility
       - Ranking Agent provides interim rankings
    3. After four rounds, run a tournament where each idea faces 10 random opponents
    4. Calculate final ELO ratings and present ideas in order of rating
    5. After the tournament, the Meta-review Agent generates a final overview
       of the top 5 ideas by ELO rating
    6. Generate comprehensive final reports for each idea in the scientia directory
    """
    # Generate a short problem name and create a directory for this run
    scientia_dir = None
    try:
        problem_name = generate_problem_name(research_goal)
        scientia_dir = create_scientia_directory(problem_name)
        print(f"Created directory: {scientia_dir} for tracking idea evolution\n")
    except Exception as e:
        print(f"Warning: Failed to create directory: {e}")
    
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
            
            # Log each newly generated idea to its own file
            if scientia_dir:
                try:
                    for i, idea in enumerate(ideas):
                        log_idea(scientia_dir, i+1, idea, "Initial Generation", round_idx+1)
                except Exception as e:
                    print(f"Warning: Failed to log ideas: {e}")
                    
            print("=== GENERATION AGENT OUTPUT ===")
            print(generation_output)
            print("")
        else:
            # In subsequent rounds, we evolve all existing ideas
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

            # Log the evolution of each idea
            if scientia_dir:
                try:
                    for i, idea in enumerate(evolved_ideas):
                        log_idea(scientia_dir, i+1, idea, "Evolution", round_idx+1)
                except Exception as e:
                    print(f"Warning: Failed to log evolved ideas: {e}")

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
        
        # Log the reflection feedback for each idea
        if scientia_dir:
            try:
                for i, idea in enumerate(ideas):
                    reflection_entry = f"{idea}\n\n--- REFLECTION FEEDBACK ---\n\n{reflection_output}"
                    log_idea(scientia_dir, i+1, reflection_entry, "Reflection", round_idx+1)
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
            user_prompt=proximity_prompt
        )
        print("=== PROXIMITY CHECK AGENT OUTPUT ===")
        print(proximity_output)
        print("")
        
        # Log proximity check results
        if scientia_dir:
            try:
                for i, idea in enumerate(ideas):
                    proximity_entry = f"{idea}\n\n--- PROXIMITY CHECK FEEDBACK ---\n\n{proximity_output}"
                    log_idea(scientia_dir, i+1, proximity_entry, "Proximity Check", round_idx+1)
            except Exception as e:
                print(f"Warning: Failed to log proximity check: {e}")

        # 4) Ranking (skip for first 3 rounds)
        if round_idx >= 3:  # Only do ranking from round 4 onwards
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
            
            # Log ranking information
            if scientia_dir:
                try:
                    for i, idea in enumerate(ideas):
                        ranking_entry = f"{idea}\n\n--- RANKING FEEDBACK (ROUND {round_idx+1}) ---\n\n{ranking_output}"
                        log_idea(scientia_dir, i+1, ranking_entry, "Ranking", round_idx+1)
                except Exception as e:
                    print(f"Warning: Failed to log ranking: {e}")

            # Reorder ideas based on ranking
            ideas_ordered = parse_ideas_order_from_ranking(ranking_output, ideas)
            ideas = ideas_ordered
        else:
            print("=== SKIPPING RANKING FOR THIS ROUND ===")
            print("Focusing on improvement only in the first three rounds.")
            print("")
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
        
        # Log the supervisor's summary
        if scientia_dir:
            try:
                for i, idea in enumerate(ideas):
                    summary_entry = f"{idea}\n\n--- SUPERVISOR SUMMARY (ROUND {round_idx+1}) ---\n\n{round_summary}"
                    log_idea(scientia_dir, i+1, summary_entry, "Round Summary", round_idx+1)
            except Exception as e:
                print(f"Warning: Failed to log round summary: {e}")

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
    
    def initialize_elo_ratings(ideas: List[str]) -> Dict[str, float]:
        """Initialize each idea with a base ELO rating of 1500."""
        return {idea: 1500.0 for idea in ideas}

    def calculate_elo_update(rating_a: float, rating_b: float, score: float, k: float = 64.0) -> Tuple[float, float]:
        '''
        Calculate updated ELO ratings based on the comparison score.
        score should be between 0 and 1, representing idea_a's performance against idea_b.
        '''
        expected_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
        update = k * (score - expected_a)
        return rating_a + update, rating_b - update
    
    def parse_tournament_scores(result: str) -> Tuple[IdeaScore, IdeaScore]:
        '''Parse the tournament agent's response to extract scores for both ideas.'''
        import re
        
        # Initialize score lists
        scores_a = []
        scores_b = []
        
        # Look for score patterns like "Criterion N (...): Idea A = X, Idea B = Y"
        score_pattern = r'(?i)criterion\s*\d+.*?(?::|[-=]).*?(?:idea\s*a|a)\s*[-=]\s*(\d+)[,\s]+(?:idea\s*b|b)\s*[-=]\s*(\d+)'
        
        # Find all score pairs in the text
        matches = list(re.finditer(score_pattern, result))
        
        for match in matches:
            try:
                score_a = float(match.group(1))
                score_b = float(match.group(2))
                # Validate scores are in range 1-10
                if 1 <= score_a <= 10 and 1 <= score_b <= 10:
                    scores_a.append(score_a)
                    scores_b.append(score_b)
            except (ValueError, IndexError):
                # Skip any parsing errors for individual scores
                print(f"WARNING: Skipping invalid score match: {match.group(0)}")
        
        # If we didn't find exactly 8 scores (our criteria count), try to fill in missing ones
        if len(scores_a) < 8 or len(scores_b) < 8:
            print("WARNING: Failed to parse all 8 scores from response. Found:")
            print(f"Idea A: {len(scores_a)} scores, Idea B: {len(scores_b)} scores")
            print("Response:", result)
            
            # Try to extract scores with a more lenient pattern if the primary one failed
            if len(scores_a) < 8 or len(scores_b) < 8:
                lenient_pattern = r'(?i)a\s*[=:]\s*(\d+)[,\s.]*b\s*[=:]\s*(\d+)'
                lenient_matches = list(re.finditer(lenient_pattern, result))
                
                for match in lenient_matches:
                    if len(scores_a) >= 8 and len(scores_b) >= 8:
                        break
                    
                    try:
                        score_a = float(match.group(1))
                        score_b = float(match.group(2))
                        # Validate scores are in range 1-10
                        if 1 <= score_a <= 10 and 1 <= score_b <= 10:
                            if match.group(0) not in [m.group(0) for m in matches]:  # Avoid duplicates
                                scores_a.append(score_a)
                                scores_b.append(score_b)
                    except (ValueError, IndexError):
                        pass
            
            # If still incomplete, fill in missing scores
            while len(scores_a) < 8:
                print(f"Adding default score for Idea A (position {len(scores_a)+1})")
                scores_a.append(5.0)  # Default to average/neutral
            
            while len(scores_b) < 8:
                print(f"Adding default score for Idea B (position {len(scores_b)+1})")
                scores_b.append(5.0)  # Default to average/neutral

        # If we have more than 8 scores, trim to the first 8
        if len(scores_a) > 8:
            print(f"WARNING: Found {len(scores_a)} scores for Idea A, trimming to 8")
            scores_a = scores_a[:8]
        
        if len(scores_b) > 8:
            print(f"WARNING: Found {len(scores_b)} scores for Idea B, trimming to 8")
            scores_b = scores_b[:8]
        
        return (
            IdeaScore(*scores_a),
            IdeaScore(*scores_b)
        )

    def parse_ideas_from_tournament_text(text: str) -> List[str]:
        '''Extract individual hypotheses from the tournament text.'''
        ideas = []
        # Look for hypothesis sections marked with "**Hypothesis:**"
        hypothesis_pattern = r'\*\*Hypothesis:\*\*\s*([^[]*?)\['
        matches = re.finditer(hypothesis_pattern, text)
        for match in matches:
            hypothesis = match.group(1).strip()
            if hypothesis:
                ideas.append(hypothesis)
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
        
    def run_tournament(ideas: List[str], tournament_agent_prompt: str, scientia_dir: Optional[str] = None) -> List[Tuple[str, float]]:
        '''
        Run a tournament where each idea is compared against 10 random other ideas.
        Returns list of (idea, final_elo_rating) tuples sorted by rating.
        Outputs detailed results for each matchup.
        '''
        # Extract hypotheses if needed
        if len(ideas) == 1 and '**Hypothesis:**' in ideas[0]:
            ideas = parse_ideas_from_tournament_text(ideas[0])
            if len(ideas) < 2:
                print("ERROR: Could not extract multiple hypotheses from the text.")
                return [(ideas[0], 1500.0)]
        
        # Filter out incomplete or invalid ideas
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
                
                # Log the tournament matchup results if scientia_dir is available
                if scientia_dir:
                    try:
                        # Log for idea A
                        matchup_log_a = (
                            f"Tournament Matchup vs Idea {ideas.index(idea_b)+1}\n\n"
                            f"Opponent: {idea_b}\n\n"
                            f"Scores by Criterion:\n"
                        )
                        for criterion, score_a, score_b in zip(criteria, list(scores_a), list(scores_b)):
                            matchup_log_a += f"{criterion}: {score_a:.1f} vs {score_b:.1f}\n"
                        
                        matchup_log_a += f"\nVector-based score: {vector_score:.3f}\n"
                        matchup_log_a += f"ELO update: {old_rating_a:.1f} → {new_rating_a:.1f} ({new_rating_a - old_rating_a:+.1f})"
                        
                        log_idea(scientia_dir, i+1, matchup_log_a, "Tournament Matchup", elo_score=new_rating_a)
                        
                        # Log for idea B
                        j = ideas.index(idea_b)
                        matchup_log_b = (
                            f"Tournament Matchup vs Idea {i+1}\n\n"
                            f"Opponent: {idea_a}\n\n"
                            f"Scores by Criterion:\n"
                        )
                        for criterion, score_b, score_a in zip(criteria, list(scores_b), list(scores_a)):
                            matchup_log_b += f"{criterion}: {score_b:.1f} vs {score_a:.1f}\n"
                        
                        matchup_log_b += f"\nVector-based score: {1-vector_score:.3f}\n"
                        matchup_log_b += f"ELO update: {old_rating_b:.1f} → {new_rating_b:.1f} ({new_rating_b - old_rating_b:+.1f})"
                        
                        log_idea(scientia_dir, j+1, matchup_log_b, "Tournament Matchup", elo_score=new_rating_b)
                    except Exception as e:
                        print(f"Warning: Failed to log tournament matchup: {e}")
                        traceback.print_exc()
        
        # Sort ideas by final ELO rating
        return sorted(
            [(idea, rating) for idea, rating in elo_ratings.items()],
            key=lambda x: x[1],
            reverse=True
        )
    # Run the tournament
    tournament_results = run_tournament(ideas, get_tournament_agent_prompt(), scientia_dir)
    
    # Log final tournament results for each idea
    if scientia_dir:
        try:
            print("\nLogging final tournament results...")
            for i, (idea, rating) in enumerate(tournament_results):
                # Find the idea's index in the original list
                original_idx = ideas.index(idea) if idea in ideas else i
                tournament_entry = f"Final ELO Rating: {rating:.1f}\n\nRank: {i+1} out of {len(ideas)}\n\n{idea}"
                log_idea(scientia_dir, original_idx+1, tournament_entry, "Final Tournament Results", elo_score=rating)
        except Exception as e:
            print(f"Warning: Failed to log final tournament results: {e}")
    
    # Output final rankings with detailed scores
    print("\n=== FINAL ELO RANKINGS ===")
    print("-" * 80)
    for i, (idea, rating) in enumerate(tournament_results, 1):
        print(f"\n{i}. Final ELO Rating: {rating:.1f}")
        # Extract just the title and key idea for display
        sections = parse_structured_idea(idea)
        title = sections.get("title", "")
        key_idea = sections.get("key_idea", "")
        # Extract just the title and key idea for display
        sections = parse_structured_idea(idea)
        title = sections.get("title", "")
        key_idea = sections.get("key_idea", "")
        
        if title:
            print(f"Title: {title}")
        print("Key Idea:")
        print(textwrap.fill(key_idea or idea[:200] + "...", width=80, initial_indent="  ", subsequent_indent="  "))
    print("-" * 80)
    
    # Get the top 5 ideas for meta-review
    top_5_ideas = tournament_results[:5]
    final_ideas_text = "\n\n".join([f"{i+1}. {idea}" for i, (idea, _) in enumerate(top_5_ideas)])
    
    # Create meta-review prompt for final analysis
    meta_prompt = (
        f"Here are the final top 5 ideas based on tournament results:\n\n"
        f"{final_ideas_text}\n\n"
        "Please provide a comprehensive meta-review that addresses the following:\n\n"
        "1. Summarize each of the top 5 ideas, highlighting their core hypotheses and key innovations\n"
        "2. Analyze the strengths and limitations of each idea, noting potential impact and feasibility\n"
        "3. Identify cross-cutting themes or complementary approaches across these ideas\n"
        "4. Suggest practical next steps for validating or implementing each idea\n"
        "5. Recommend potential collaborations or interdisciplinary connections\n\n"
        "For each idea, include relevant citations from the existing references, and suggest "
        "additional key literature in the format [Author Year] that would strengthen the research. "
        "Your meta-review should synthesize the final, evolved state of each idea, including "
        "improvements made throughout the iterative process."
    )
    
    # Call the meta-review agent
    meta_review_output = call_agent(
        get_meta_review_agent_prompt(),
        user_prompt=meta_prompt
    )
    
    print("\n=== META-REVIEW AGENT OUTPUT (TOP 5 BY ELO) ===")
    print(meta_review_output)
    # Log the meta-review
    if scientia_dir:
        try:
            # Save meta-review to a separate file
            meta_review_file = os.path.join(scientia_dir, "meta_review.md")
            with open(meta_review_file, 'w', encoding='utf-8') as f:
                f.write("# Meta-Review of Top 5 Ideas\n\n")
                f.write("## Top 5 Ideas by ELO Rating\n\n")
                for i, (idea, rating) in enumerate(tournament_results[:5], 1):
                    f.write(f"### {i}. Idea (ELO: {rating:.1f})\n\n")
                    f.write(f"{idea}\n\n")
                f.write("## Meta-Review Analysis\n\n")
                f.write(meta_review_output)
            
            print(f"\nMeta-review saved to: {meta_review_file}")
            
            # Also log the meta-review for each of the top 5 ideas
            for i, (idea, rating) in enumerate(tournament_results[:5]):
                original_idx = ideas.index(idea) if idea in ideas else i
                meta_entry = f"Meta-Review (Top 5):\n\n{meta_review_output}"
                log_idea(scientia_dir, original_idx+1, meta_entry, "Meta-Review", elo_score=rating)
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
                        generate_final_report(scientia_dir, idea_num, idea, rating, log_file_path)
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
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scientia_gpt41_v3.py <research_goal> [num_ideas]")
        print("  num_ideas: Optional number of ideas to generate (default: 20)")
        sys.exit(1)

    user_research_goal = ' '.join(sys.argv[1:-1]) if len(sys.argv) > 2 and sys.argv[-1].isdigit() else ' '.join(sys.argv[1:])
    num_ideas = int(sys.argv[-1]) if len(sys.argv) > 2 and sys.argv[-1].isdigit() else 20

    print(f"Generating {num_ideas} ideas for research goal: {user_research_goal}")
    run_co_scientist_workflow(
        research_goal=user_research_goal,
        num_ideas=num_ideas
    )
