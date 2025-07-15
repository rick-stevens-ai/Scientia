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
import argparse
import yaml
import uuid
from pathlib import Path
from openai import OpenAI
from openai import APIError, APITimeoutError, APIConnectionError, RateLimitError
from typing import List, Dict, Any, Tuple, Optional, Union, Callable, Set
from dataclasses import dataclass
import random

from typing import NamedTuple

# Define tournament criteria list for consistent use throughout the code
# Generic scientific criteria applicable across disciplines
TOURNAMENT_CRITERIA = [
    "Empirical Support",         # Consistency with existing evidence and data
    "Theoretical Coherence",     # Internal logical consistency and clarity
    "Explanatory Power",         # Ability to explain observed phenomena
    "Predictive Capability",     # Ability to make testable predictions
    "Falsifiability",            # Potential to be disproven by evidence
    "Parsimony",                 # Simplicity and elegance (Occam's Razor)
    "Generalizability",          # Applicability beyond initial scope
    "Methodological Rigor",      # Sound scientific methods and procedures
    "Innovation",                # Originality and advancement over existing ideas
    "Problem-Solving Utility",   # Practical application to solve problems
    "Interdisciplinary Impact",  # Relevance across multiple fields
    "Ethical Considerations",    # Ethical implications and responsibilities
    "Scalability",               # Performance across different scales
    "Replicability",             # Potential for results to be reproduced
    "Theoretical Foundation",    # Grounding in established scientific knowledge
    "Technological Feasibility", # Practicality of implementation
    "Risk Assessment",           # Potential drawbacks and limitations
    "Sustainability",            # Long-term viability and resource efficiency
    "Societal Relevance",        # Impact on human society and wellbeing
    "Future Research Potential"  # Capacity to generate new research directions
]

# IdeaScore class definition for tournament scoring
class IdeaScore(NamedTuple):
    # Evidence and theoretical foundation
    empirical_support: float         # Consistency with existing evidence
    theoretical_coherence: float     # Internal logical consistency
    explanatory_power: float         # Ability to explain phenomena
    predictive_capability: float     # Ability to make predictions
    falsifiability: float            # Potential to be disproven

    # Scientific quality and applicability
    parsimony: float                 # Simplicity and elegance
    generalizability: float          # Applicability beyond initial scope
    methodological_rigor: float      # Sound scientific methods
    innovation: float                # Originality over existing ideas
    problem_solving_utility: float   # Practical application value

    # Impact and integration
    interdisciplinary_impact: float  # Relevance across multiple fields
    ethical_considerations: float    # Ethical implications
    scalability: float               # Performance across different scales
    replicability: float             # Reproducibility of results
    theoretical_foundation: float    # Grounding in established knowledge

    # Implementation and future potential
    technological_feasibility: float # Practicality of implementation
    risk_assessment: float           # Potential limitations
    sustainability: float            # Long-term viability
    societal_relevance: float        # Impact on human society
    future_research_potential: float # Capacity to generate new research
@dataclass
class IdeaMetadata:
    """Tracks metadata for a single idea through its evolution"""
    id: int  # Numeric identifier for this idea (for backward compatibility)
    unique_id: str  # Globally unique identifier for this idea
    parent_id: Optional[int]  # ID of parent idea if this is a refinement
    parent_unique_id: Optional[str]  # Unique ID of parent idea if this is a refinement
    creation_time: datetime.datetime
    generation_type: str  # Either "initial", "refined", or "new"
    refinement_count: int = 0
    tournament_matches: int = 0
    elo_history: List[float] = None
    criteria_scores: Optional[Dict[str, float]] = None  # Scores for scientific criteria
    
    def __post_init__(self):
        if self.elo_history is None:
            self.elo_history = [1200.0]  # Initial ELO rating
        if self.criteria_scores is None:
            self.criteria_scores = {}  # Empty dict for scores


class IdeaEvolution:
    """Manages the evolution and tracking of ideas through refinement cycles"""
    def __init__(self):
        self.ideas: Dict[int, str] = {}  # Current idea texts by numeric ID
        self.metadata: Dict[int, IdeaMetadata] = {}  # Idea metadata by numeric ID
        self.unique_id_map: Dict[str, int] = {}  # Maps unique IDs to numeric IDs
        self.next_id: int = 1
        self.refined_pairs: Set[tuple[int, int]] = set()  # Track refinement relationships
        
    def add_initial_idea(self, idea_text: str) -> int:
        """Add an initial idea and return its ID"""
        idea_id = self.next_id
        self.next_id += 1
        unique_id = generate_unique_idea_id(idea_text)
        self.ideas[idea_id] = idea_text
        self.metadata[idea_id] = IdeaMetadata(
            id=idea_id,
            unique_id=unique_id,
            parent_id=None,
            parent_unique_id=None,
            creation_time=datetime.datetime.now(),
            generation_type="initial"
        )
        self.unique_id_map[unique_id] = idea_id
        return idea_id
        
    def add_refined_idea(self, original_id: int, refined_text: str) -> int:
        """Add a refined version of an existing idea"""
        if original_id not in self.ideas:
            raise ValueError(f"Original idea {original_id} not found")
            
        idea_id = self.next_id
        self.next_id += 1
        unique_id = generate_unique_idea_id(refined_text)
        self.ideas[idea_id] = refined_text
        
        # Get parent unique ID if available
        parent_unique_id = self.metadata[original_id].unique_id if original_id in self.metadata else None
        
        self.metadata[idea_id] = IdeaMetadata(
            id=idea_id,
            unique_id=unique_id,
            parent_id=original_id,
            parent_unique_id=parent_unique_id,
            creation_time=datetime.datetime.now(),
            generation_type="refined"
        )
        self.refined_pairs.add((original_id, idea_id))
        self.unique_id_map[unique_id] = idea_id
        
        # Update refinement count for original idea
        if original_id in self.metadata:
            self.metadata[original_id].refinement_count += 1
        return idea_id
        
    def add_new_idea(self, idea_text: str) -> int:
        """Add a completely new idea generated during evolution"""
        idea_id = self.next_id
        self.next_id += 1
        unique_id = generate_unique_idea_id(idea_text)
        self.ideas[idea_id] = idea_text
        self.metadata[idea_id] = IdeaMetadata(
            id=idea_id,
            unique_id=unique_id,
            parent_id=None,
            parent_unique_id=None,
            creation_time=datetime.datetime.now(),
            generation_type="new"
        )
        self.unique_id_map[unique_id] = idea_id
        return idea_id
        
    def get_idea_history(self, idea_id: int) -> List[str]:
        """Get the evolution history of an idea"""
        if idea_id not in self.ideas:
            raise ValueError(f"Idea {idea_id} not found")
            
        history = []
        current_id = idea_id
        while current_id is not None:
            if current_id in self.ideas:
                history.append(self.ideas[current_id])
                current_id = self.metadata[current_id].parent_id if current_id in self.metadata else None
            else:
                break
        return list(reversed(history))  # Return in chronological order
        
    def update_elo(self, idea_id: int, new_elo: float):
        """Update the ELO history for an idea"""
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        self.metadata[idea_id].elo_history.append(new_elo)
        
    def record_tournament_match(self, idea_id: int):
        """Record that an idea participated in a tournament match"""
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        self.metadata[idea_id].tournament_matches += 1
        
    def update_criteria_scores(self, idea_id: int, scores: Dict[str, float]):
        """Update the scientific criteria scores for an idea"""
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        self.metadata[idea_id].criteria_scores.update(scores)
        
    def get_all_ideas(self) -> Dict[int, str]:
        """Get all current ideas"""
        return self.ideas.copy()
        
    def get_metadata(self, idea_id: int) -> IdeaMetadata:
        """Get metadata for a specific idea"""
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        return self.metadata[idea_id]
        
    def get_id_by_unique_id(self, unique_id: str) -> Optional[int]:
        """Get the numeric ID for a given unique ID"""
        return self.unique_id_map.get(unique_id)
        
    def get_unique_id(self, idea_id: int) -> Optional[str]:
        """Get the unique ID for a given numeric ID"""
        if idea_id not in self.metadata:
            return None
        return self.metadata[idea_id].unique_id

# Function to generate a unique ID for an idea
def generate_unique_idea_id(idea_text: str) -> str:
    """
    Generate a unique ID for an idea based on its content and a timestamp.
    
    Args:
        idea_text: The text content of the idea
        
    Returns:
        A string containing a unique identifier for the idea
    """
    # Create a base for the hash using the idea text and current time
    base = f"{idea_text}_{datetime.datetime.now().isoformat()}"
    # Generate a hash of the base string
    idea_hash = hashlib.md5(base.encode('utf-8')).hexdigest()[:8]
    # Combine with a UUID component for uniqueness
    unique_id = f"{idea_hash}-{str(uuid.uuid4())[:8]}"
    return unique_id

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
                                    "Consistency with existing evidence and data",
                                    "Internal logical consistency and clarity",
                                    "Ability to explain observed phenomena",
                                    "Ability to make testable predictions",
                                    "Potential to be disproven by evidence",
                                    "Simplicity and elegance (Occam's Razor)",
                                    "Applicability beyond initial scope",
                                    "Sound scientific methods and procedures",
                                    "Originality and advancement over existing ideas",
                                    "Practical application to solve problems",
                                    "Relevance across multiple fields",
                                    "Ethical implications and responsibilities",
                                    "Performance across different scales",
                                    "Potential for results to be reproduced",
                                    "Grounding in established scientific knowledge",
                                    "Practicality of implementation",
                                    "Potential drawbacks and limitations",
                                    "Long-term viability and resource efficiency",
                                    "Impact on human society and wellbeing",
                                    "Capacity to generate new research directions"
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

# Function to load model configurations from YAML file
def load_model_configs(yaml_file='model_servers.yaml'):
    """
    Load model configurations from a YAML file.
    
    Args:
        yaml_file: Path to the YAML configuration file
        
    Returns:
        Dictionary mapping model shortnames to their configurations
    """
    try:
        with open(yaml_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Create a dictionary mapping shortnames to full configurations
        models = {}
        for server in config.get('servers', []):
            if 'shortname' in server:
                models[server['shortname']] = server
        
        return models
    except Exception as e:
        print(f"Error loading model configurations: {e}")
        traceback.print_exc()
        return {}

# Initialize configuration variables
MODEL_TIMEOUT = 120.0  # Timeout in seconds (increased to handle larger responses)
MAX_RETRIES_TIMEOUT = 3  # Maximum retries for timeout errors

# Client instances for different models
main_client = None
reflection_client = None
MAIN_MODEL_ID = None
REFLECTION_MODEL_ID = None

# These will be set after parsing command line arguments
MODEL_CONFIG = None
MODEL_ID = None
client = None

def initialize_client(model_shortname='gpt41', is_reflection=False, config_file='model_servers.yaml'):
    """
    Initialize the OpenAI client based on the selected model configuration.
    
    Args:
        model_shortname: Shortname of the model to use
        is_reflection: Whether this client is for the reflection agent
        config_file: Path to the model servers configuration file
        
    Returns:
        Tuple of (client, model_id, config)
    """
    # Module-level variables are already global
    
    # Load model configurations
    models = load_model_configs(config_file)
    
    if not models:
        print("Error: No model configurations found. Check model_servers.yaml file.")
        sys.exit(1)
    
    # Validate model selection
    if model_shortname not in models:
        print(f"Error: Model '{model_shortname}' not found in configuration.")
        print(f"Available models: {', '.join(models.keys())}")
        sys.exit(1)
    
    config = models[model_shortname]
    client_type = "Reflection" if is_reflection else "Main"
    print(f"Using {client_type} model: {model_shortname} ({config['openai_model']})")
    
    # Handle API key - either from env var or literal
    api_key = config['openai_api_key']
    if api_key.startswith("${") and api_key.endswith("}"):
        # Extract environment variable name
        env_var = api_key[2:-1]
        api_key = os.getenv(env_var)
        if not api_key:
            print(f"Error: Environment variable {env_var} not set")
            sys.exit(1)
    
    # Set model ID if this is the main model
    if not is_reflection:
        MODEL_ID = config['openai_model']
    
    # Create OpenAI client
    try:
        return OpenAI(
            api_key=api_key,
            base_url=config['openai_api_base']
        ), config['openai_model'], config
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        traceback.print_exc()
        sys.exit(1)
# Debug and logging settings
DEBUG_MODE = False      # Disable detailed logging by default (can be enabled via --debug flag)
CHECKPOINT_FREQ = True  # Enable state checkpointing
AUTO_BACKUP = True      # Enable automatic backups
MAX_BACKUPS = 3         # Maximum number of backup files to keep
RECOVERY_ENABLED = True # Enable automatic recovery from checkpoints
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

def clean_section_content(content: str) -> str:
    """
    Clean section content by removing embedded bullet points that reference other sections.
    
    Args:
        content: Raw section content that might contain bullet points with other sections
        
    Returns:
        Cleaned content with only the main section text
    """
    if not content:
        return content
    
    # Check for the first pattern - bullet points that explicitly reference other sections
    section_bullet_pattern = r'(?:\n\s*[-•*]\s*|\s*[-•*]\s+)(?:Paragraph \d+|Key Idea|Approach|Key References):'
    section_bullet_match = re.search(section_bullet_pattern, content)
    
    # Check for any bullet points that might be part of a list
    general_bullet_pattern = r'\n\s*[-•*]\s+'
    general_bullet_match = re.search(general_bullet_pattern, content)
    
    # If we found any bullet points
    if section_bullet_match or general_bullet_match:
        # If we found a section bullet, use that
        if section_bullet_match:
            # Return only the content before the first bullet point
            return content[:section_bullet_match.start()].strip()
        
        # Otherwise, check if the general bullet contains another section name
        elif general_bullet_match:
            after_bullet = content[general_bullet_match.end():]
            # If the text after the bullet appears to be another section or contains a section reference
            if re.search(r'(?:Paragraph \d+|Key Idea|Approach|Key References)\b', after_bullet):
                # Return only the content before the bullet point
                return content[:general_bullet_match.start()].strip()
    
    return content

def parse_structured_idea(idea_text: str) -> Dict[str, str]:
    """
    Parse a structured idea text into its component parts.
    
    Args:
        idea_text: Text of a single idea with structured sections
        
    Returns:
        Dictionary with keys for each section: title, key_idea, paragraph_1, paragraph_2, paragraph_3, 
        paragraph (for backward compatibility), approach, references
    """
    # Remove any duplicated paragraph markers that might have formatting issues
    # This fixes issues like "**Paragraph**: 1**:" which should be "**Paragraph 1**:"
    idea_text = re.sub(r'\*\*Paragraph\*\*:\s*(\d+)\*\*:', r'**Paragraph \1**:', idea_text)
    
    # Pre-process to handle nested bulleted lists
    # This additional preprocessing helps catch repeated sections with bullet points
    cleaned_lines = []
    current_section = None
    skip_line = False
    
    for line in idea_text.split('\n'):
        # Check if this line starts a new section
        section_match = re.search(r'\*\*([^*]+)\*\*:', line)
        if section_match:
            current_section = section_match.group(1).strip()
            skip_line = False
            cleaned_lines.append(line)
        # Check if this is a bullet point that references another section
        elif re.search(r'^\s*[-•*]\s+(?:Paragraph \d+|Key Idea|Approach|Key References):', line):
            skip_line = True
        # If we're in skip mode and this line continues a bullet point, skip it too
        elif skip_line and (line.strip().startswith('-') or not line.strip()):
            continue
        # Otherwise include the line
        else:
            if not skip_line:
                cleaned_lines.append(line)
    
    # Rejoin the cleaned lines
    idea_text = '\n'.join(cleaned_lines)
    
    sections = {
        "title": "",
        "key_idea": "",
        "paragraph_1": "",
        "paragraph_2": "",
        "paragraph_3": "",
        "paragraph": "",  # For backward compatibility
        "approach": "",
        "references": ""
    }
    
    # First check if the text starts with a title section
    title_starts_with = False
    
    title_patterns = [
        r'^\s*(?:\*\*)?Title(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?Key Idea(?:\*\*)?:?|\Z)',
        r'^\s*(?:\*\*)?(?:Title|Heading|Name|Topic)(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?Key Idea(?:\*\*)?:?|\Z)'
    ]
    
    for pattern in title_patterns:
        title_match = re.search(pattern, idea_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title_starts_with = True
            sections["title"] = title_match.group(1).strip()
            # If we find a title at the start, remove it from the text for remaining parsing
            idea_text = re.sub(pattern, '', idea_text, count=1, flags=re.IGNORECASE | re.DOTALL).strip()
            break
    
    # If the title doesn't start the text, extract it wherever it appears
    if not title_starts_with:
        title_pattern = r'(?:\*\*)?Title(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?(?:Key Idea|Hypothesis|Paragraph)(?:\*\*)?:?|\Z)'
        title_match = re.search(title_pattern, idea_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            sections["title"] = title_match.group(1).strip()
    
    # Extract remaining sections using regex patterns with section headers
    key_idea_pattern = r'(?:\*\*)?Key Idea(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?(?:Paragraph 1|Paragraph)(?:\*\*)?:?|\Z)'
    paragraph_1_pattern = r'(?:\*\*)?Paragraph 1(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?Paragraph 2(?:\*\*)?:?|\Z)'
    paragraph_2_pattern = r'(?:\*\*)?Paragraph 2(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?Paragraph 3(?:\*\*)?:?|\Z)'
    paragraph_3_pattern = r'(?:\*\*)?Paragraph 3(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?Approach(?:\*\*)?:?|\Z)'
    paragraph_pattern = r'(?:\*\*)?Paragraph(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?Approach(?:\*\*)?:?|\Z)'
    approach_pattern = r'(?:\*\*)?Approach(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?(?:Key References|References)(?:\*\*)?:?|\Z)'
    references_pattern = r'(?:\*\*)?(?:Key References|References)(?:\*\*)?:?\s*(.*?)(?=\n\n|\Z)'
    
    # Look for sections in the text
    key_idea_match = re.search(key_idea_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    paragraph_1_match = re.search(paragraph_1_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    paragraph_2_match = re.search(paragraph_2_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    paragraph_3_match = re.search(paragraph_3_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    paragraph_match = re.search(paragraph_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    approach_match = re.search(approach_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    references_match = re.search(references_pattern, idea_text, re.IGNORECASE | re.DOTALL)
    
    # If we can't find the exact headers, try alternative headers
    if not key_idea_match:
        key_idea_match = re.search(r'(?:\*\*)?(?:Key Idea|Hypothesis|Core Idea|Main Idea)(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?|\Z)', idea_text, re.IGNORECASE | re.DOTALL)
    
    if not paragraph_match and not (paragraph_1_match or paragraph_2_match or paragraph_3_match):
        paragraph_match = re.search(r'(?:\*\*)?(?:Paragraph|Summary|Description|Explanation|Background)(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?|\Z)', idea_text, re.IGNORECASE | re.DOTALL)
        
    if not approach_match:
        approach_match = re.search(r'(?:\*\*)?(?:Approach|Methods|Testing|Implementation|Methodology)(?:\*\*)?:?\s*(.*?)(?=\n\n|\n\s*(?:\*\*)?|\Z)', idea_text, re.IGNORECASE | re.DOTALL)
    
    # Extract and clean each section
    if key_idea_match:
        sections["key_idea"] = clean_section_content(key_idea_match.group(1).strip())
    if paragraph_1_match:
        sections["paragraph_1"] = clean_section_content(paragraph_1_match.group(1).strip())
    if paragraph_2_match:
        sections["paragraph_2"] = clean_section_content(paragraph_2_match.group(1).strip())
    if paragraph_3_match:
        sections["paragraph_3"] = clean_section_content(paragraph_3_match.group(1).strip())
    if paragraph_match:
        sections["paragraph"] = clean_section_content(paragraph_match.group(1).strip())
    if approach_match:
        sections["approach"] = clean_section_content(approach_match.group(1).strip())
    if references_match:
        sections["references"] = references_match.group(1).strip()
    
    # Try to infer title from first line if we still don't have one
    if not sections["title"]:
        # First try to use the first line if it's a reasonable title length
        first_line = idea_text.split('\n')[0].strip()
        if not first_line.startswith('**') and len(first_line) < 80:
            sections["title"] = first_line
        # Otherwise try to construct from key idea
        elif sections["key_idea"]:
            key_idea_text = sections["key_idea"]
            # Take the first sentence or first 60 chars
            first_sentence = re.split(r'[.!?]', key_idea_text)[0].strip()
            if len(first_sentence) < 60:
                sections["title"] = first_sentence
            else:
                title_text = key_idea_text[:60].strip()
                if len(key_idea_text) > 60:
                    title_text += "..."
                sections["title"] = title_text
        else:
            # As a last resort use the content of paragraph1 or approach
            for field in ["paragraph_1", "approach", "paragraph"]:
                if sections[field]:
                    text = sections[field]
                    title_text = text[:50].strip()
                    if len(text) > 50:
                        title_text += "..."
                    sections["title"] = title_text
                    break
    
    # If we still don't have a title, use a generic one
    if not sections["title"] or sections["title"].lower().startswith("key references") or sections["title"].lower().startswith("paragraph"):
        sections["title"] = "Untitled Idea"
    
    # If we couldn't find any structured sections, use the whole text as the key_idea
    if not any(val for key, val in sections.items() if key != "title" and val):
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
    
    # Include numbered paragraphs
    has_numbered_paragraphs = False
    if sections.get("paragraph_1"):
        formatted += f"**Paragraph 1**: {sections['paragraph_1']}\n\n"
        has_numbered_paragraphs = True
    if sections.get("paragraph_2"):
        formatted += f"**Paragraph 2**: {sections['paragraph_2']}\n\n"
        has_numbered_paragraphs = True
    if sections.get("paragraph_3"):
        formatted += f"**Paragraph 3**: {sections['paragraph_3']}\n\n"
        has_numbered_paragraphs = True
    
    # For backward compatibility with older format
    # Only include if we don't already have any numbered paragraphs
    if not has_numbered_paragraphs and sections.get("paragraph"):
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
    """Helper function to verify the number of ideas and enforce the expected count."""
    if len(ideas) != expected_count:
        print(f"Warning: Expected {expected_count} ideas, but found {len(ideas)}.")
        if len(ideas) > expected_count:
            # Trim the list to the expected count
            print(f"Trimming to the requested {expected_count} ideas.")
            return ideas[:expected_count]
        else:
            # If we have fewer ideas than expected, we'll keep them all
            print(f"Only found {len(ideas)} ideas, fewer than the requested {expected_count}.")
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
    Uses a hybrid approach that considers both overall score magnitude and 
    criteria-by-criteria comparison to ensure meaningful differentiation.
    '''
    # Convert scores to vectors
    vec_a = list(scores_a)
    vec_b = list(scores_b)
    
    # Add small random noise to each score to prevent exact ties
    # This helps ensure meaningful differentiation between ideas
    # The noise is small enough (±0.05) that it won't significantly affect valid comparisons
    vec_a = [a + random.uniform(-0.05, 0.05) for a in vec_a]
    vec_b = [b + random.uniform(-0.05, 0.05) for b in vec_b]
    
    # Count criteria where each idea is stronger
    a_wins = sum(1 for a, b in zip(vec_a, vec_b) if a > b)
    b_wins = sum(1 for a, b in zip(vec_a, vec_b) if b > a)
    ties = sum(1 for a, b in zip(vec_a, vec_b) if a == b)
    
    # Calculate vector magnitudes
    mag_a = sum(x for x in vec_a)  # Simple sum works better than Euclidean for this case
    mag_b = sum(x for x in vec_b)
    
    # Normalize to prevent division by zero
    total_mag = mag_a + mag_b
    if total_mag == 0:
        return 0.5  # If both vectors are zero, return draw
    
    # Calculate magnitude-based score
    magnitude_score = mag_a / total_mag
    
    # Calculate win-count based score
    win_count_score = (a_wins + 0.5 * ties) / (a_wins + b_wins + ties)
    
    # Return combined score (60% magnitude, 40% win count)
    # This balances both the overall strength and breadth of criteria advantages
    # and ensures even small differences result in meaningful ELO changes
    final_score = 0.6 * magnitude_score + 0.4 * win_count_score
    
    # Ensure score is never exactly 0.5 by adding minimal offset in random direction
    # This helps ensure the ELO ratings will always change
    if abs(final_score - 0.5) < 0.01:
        final_score = 0.5 + (0.01 * (1 if random.random() > 0.5 else -1))
    
    return final_score
    
def calculate_elo_update(rating_a: float, rating_b: float, score: float, k: float = 64.0) -> Tuple[float, float]:
    '''
    Calculate updated ELO ratings based on the comparison score.
    score should be between 0 and 1, representing idea_a's performance against idea_b.
    
    The K-factor determines how much ratings can change in each match.
    A higher K-factor will result in more volatile ratings.
    '''
    # Adjust K-factor based on rating difference to make matches between unequal ideas
    # have more impact (encourages mobility in the rankings)
    rating_diff = abs(rating_a - rating_b)
    adjusted_k = k
    
    # If the rating difference is large, increase the K-factor to allow for
    # more significant rating changes when unexpected outcomes occur
    if rating_diff > 200:
        adjusted_k = k * 1.5
    
    # Calculate expected outcome based on current ratings
    expected_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
    
    # Calculate rating updates: adjust more when score is farther from expected
    update = adjusted_k * (score - expected_a)
    
    # Ensure minimum update to avoid stagnant ratings
    # (when ideas have very similar ratings but still different performances)
    if abs(update) < 0.5 and abs(score - 0.5) > 0.05:
        # If there was a clear winner (not close to a draw) but the update is small,
        # apply a minimum update in the appropriate direction
        update = 0.5 if update > 0 else -0.5
    
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
        derived_ideas = []
        
        if idea_tracker:
            # Look for this idea in the tracker
            current_idea_id = None
            for id, text in idea_tracker.get_all_ideas().items():
                if text == idea_text:
                    idea_metadata = idea_tracker.get_metadata(id)
                    idea_unique_id = getattr(idea_metadata, "unique_id", None)
                    criteria_scores = getattr(idea_metadata, "criteria_scores", {}) or {}
                    current_idea_id = id
                    break
            
            # Find ideas derived from this one
            if current_idea_id is not None:
                for id, metadata in idea_tracker.metadata.items():
                    if getattr(metadata, "parent_id", None) == current_idea_id:
                        derived_idea_text = idea_tracker.ideas.get(id, "")
                        if derived_idea_text:
                            derived_sections = parse_structured_idea(derived_idea_text)
                            derived_ideas.append({
                                "id": id,
                                "title": derived_sections.get("title", "Untitled"),
                                "key_idea": derived_sections.get("key_idea", ""),
                                "unique_id": getattr(metadata, "unique_id", None)
                            })
        
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

## Detailed Description

"""
        # Add the three paragraphs if they exist, or fall back to the single paragraph
        if sections.get("paragraph_1") or sections.get("paragraph_2") or sections.get("paragraph_3"):
            report_content += f"### Technical Description\n\n{sections.get('paragraph_1', 'No detailed technical description available')}\n\n"
            report_content += f"### Computational/Experimental Approach\n\n{sections.get('paragraph_2', 'No detailed approach available')}\n\n"
            report_content += f"### Scientific Evaluation\n\n{sections.get('paragraph_3', 'No scientific evaluation available')}\n\n"
        else:
            report_content += f"{sections.get('paragraph', 'No detailed summary available')}\n\n"

        report_content += f"""
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
            
        # Add derived ideas section
        report_content += "\n## Ideas Derived from This Concept\n\n"
        if derived_ideas:
            report_content += "The following ideas were derived from or inspired by this concept:\n\n"
            for i, derived in enumerate(derived_ideas, 1):
                report_content += f"### {i}. Idea {derived['id']}: {derived['title']}\n\n"
                report_content += f"{derived['key_idea']}\n\n"
                report_content += f"[View full idea details](idea_{derived['id']}_final.md)\n\n"
        else:
            report_content += "No ideas were directly derived from this concept.\n\n"
        
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
    all required sections. It focuses on maximizing diversity in the generated ideas.
    """
    return (
        "You are the Generation Agent in a multi-agent AI co-scientist system. "
        "You produce new ideas and hypotheses in response to a defined "
        "research goal. Your PRIMARY objective is to MAXIMIZE DIVERSITY across ideas, "
        "ensuring each idea approaches the problem from a fundamentally different angle, "
        "theoretical framework, methodological approach, or disciplinary perspective. "
        "Avoid generating ideas that are minor variations of the same core concept. "
        "For each idea, you MUST include ALL of the following sections in this exact order:\n\n"
        "1. **Title**: A CONCISE, SPECIFIC, and UNIQUE title (5-10 words) that clearly identifies the core concept. Each title must be different from all other titles and should NOT start with phrases like 'A Study of', 'Investigation into', or similar generic openings. Make titles memorable and distinctive.\n"
        "2. **Key Idea**: A single sentence that clearly states the core hypothesis\n"
        "3. **Paragraph 1**: A detailed technical description of the idea that includes: the premise, the hypothesis, "
        "an argument for what problem it solves, and why it is novel. This should be comprehensive and technically precise.\n"
        "4. **Paragraph 2**: Explicitly tie the idea to the research goal, and layout a detailed computational or experimental "
        "approach to test or implement the idea. Include specific methodologies, techniques, and potential challenges.\n"
        "5. **Paragraph 3**: Address how the idea performs across scientific evaluation criteria, including: empirical support, "
        "theoretical coherence, explanatory power, predictive capability, falsifiability, parsimony, generalizability, "
        "methodological rigor, innovation, and future research potential.\n"
        "6. **Approach**: A concise summary of methods for implementation or testing of the hypothesis\n"
        "7. **Key References**: Relevant citations using the format [Author Year]\n\n"
        "IMPORTANT TITLE GUIDELINES:\n"
        "- Each title MUST be completely unique and distinct from all other titles\n"
        "- Titles should be specific to the hypothesis (not generic like 'FDXR Study')\n"
        "- Titles should be 5-10 words, concise but descriptive\n"
        "- Titles should NOT be full sentences, but rather noun phrases\n"
        "- Avoid starting titles with 'The', 'A', or 'An' when possible\n"
        "- DO NOT include 'Approach' or methodology details in the title\n"
        "- NEVER start the title with phrases like 'We will use' or similar\n\n"
        "Leverage existing literature, domain knowledge, and "
        "creative thinking to propose multiple distinct research directions, "
        "frameworks, or experimental designs. Strive for novelty, practicality, "
        "and scientific rigor. "
        "Include relevant citations to support your hypotheses and problem descriptions. "
        "If citing specific literature, include brief source details relevant to understanding the "
        "citation's context. These citations should be maintained throughout the "
        "refinement process. "
        "Each idea should be comprehensive, with paragraphs 1-3 containing detailed, thorough discussions that reflect "
        "deep scientific thinking. Aim for 250-350 words across these three paragraphs to ensure sufficient depth.\n\n"
        "CRITICAL: You MUST generate EXACTLY the number of ideas requested in the user prompt. Do not generate fewer "
        "or more ideas than requested. If the user asks for a specific number of ideas, you MUST generate that exact number. "
        "Ensure each idea has a PROPER, UNIQUE TITLE as the first element."
    )
def get_ranking_agent_prompt():
    """
    The Ranking Agent compares and ranks competing hypotheses or proposals,
    considering multiple criteria with emphasis on scientific merit and impact.
    """
    return (
        "You receive multiple research ideas or proposals, each containing an explicit "
        "hypothesis. Compare and rank them based on twenty key criteria: \n\n"

        "Evidence and theoretical foundation:\n"
        "(1) Empirical Support - consistency with existing evidence and data\n"
        "(2) Theoretical Coherence - internal logical consistency and clarity\n"
        "(3) Explanatory Power - ability to explain observed phenomena\n"
        "(4) Predictive Capability - ability to make testable predictions\n"
        "(5) Falsifiability - potential to be disproven by evidence\n\n"

        "Scientific quality and applicability:\n"
        "(6) Parsimony - simplicity and elegance (Occam's Razor)\n"
        "(7) Generalizability - applicability beyond initial scope\n"
        "(8) Methodological Rigor - sound scientific methods and procedures\n"
        "(9) Innovation - originality and advancement over existing ideas\n"
        "(10) Problem-Solving Utility - practical application to solve problems\n\n"

        "Impact and integration:\n"
        "(11) Interdisciplinary Impact - relevance across multiple fields\n"
        "(12) Ethical Considerations - ethical implications and responsibilities\n"
        "(13) Scalability - performance across different scales\n"
        "(14) Replicability - potential for results to be reproduced\n"
        "(15) Theoretical Foundation - grounding in established scientific knowledge\n\n"

        "Implementation and future potential:\n"
        "(16) Technological Feasibility - practicality of implementation\n"
        "(17) Risk Assessment - potential drawbacks and limitations\n"
        "(18) Sustainability - long-term viability and resource efficiency\n"
        "(19) Societal Relevance - impact on human society and wellbeing\n"
        "(20) Future Research Potential - capacity to generate new research directions\n\n"

        "For each idea, evaluate all criteria and provide a final ranking with "
        "detailed rationale emphasizing scientific merit, practical impact, and "
        "long-term potential. Pay particular attention to evidence-based evaluation "
        "and real-world applicability."
    )
def get_evolution_agent_prompt():
    """
    The Evolution Agent has two main functions: (1) refine existing ideas by simplifying, 
    extending, or combining them with other concepts, and (2) generate entirely new diverse ideas 
    to expand the solution space. Each idea must contain an explicit hypothesis statement
    with appropriate citations, and new ideas should maximize diversity.
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
        
        "3. GENERATE ADDITIONAL HIGHLY DIVERSE NEW IDEAS (Secondary Task):\n"
        "   - After refining existing ideas and creating significant-change new ideas\n"
        "   - Generate additional NEW complementary ideas to meet your target\n"
        "   - These MUST explore novel angles not covered by existing ideas\n"
        "   - MAXIMIZE DIVERSITY across theoretical approaches, methodologies, and perspectives\n"
        "   - Each new idea should be fundamentally different from all existing ideas AND from each other\n"
        "   - Focus especially on exploring completely orthogonal approaches to the research problem\n"
        "   - Ensure new ideas maintain the same structured format\n"
        "   - Include multiple relevant citations to support new hypotheses\n\n"
        
        "REQUIRED FORMAT FOR ALL IDEAS (Refined or New):\n"
        "1. **Title**: A concise, descriptive title\n"
        "2. **Key Idea**: Single sentence stating the core hypothesis\n"
        "3. **Paragraph 1**: A detailed technical description of the idea that includes: the premise, the hypothesis, "
        "an argument for what problem it solves, and why it is novel. This should be comprehensive and technically precise.\n"
        "4. **Paragraph 2**: Explicitly tie the idea to the research goal, and layout a detailed computational or experimental "
        "approach to test or implement the idea. Include specific methodologies, techniques, and potential challenges.\n"
        "5. **Paragraph 3**: Address how the idea performs across scientific evaluation criteria, including: empirical support, "
        "theoretical coherence, explanatory power, predictive capability, falsifiability, parsimony, generalizability, "
        "methodological rigor, innovation, and future research potential.\n"
        "6. **Approach**: A concise summary of methods for implementation or testing of the hypothesis\n"
        "7. **Key References**: Citations in [Author Year] format\n\n"
        
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
        "by citations in [Author Year] format. "
        "Each idea should be comprehensive, with paragraphs 1-3 containing detailed, thorough discussions that reflect "
        "deep scientific thinking. Aim for 250-350 words across these three paragraphs to ensure sufficient depth."
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
    vector-based scoring across scientific merit criteria.
    """
    return (
        "You are the Tournament Agent in a multi-agent AI co-scientist system. "
        "For each pair of ideas, evaluate them across these twenty criteria "
        "and provide numerical scores in EXACTLY this format:\n\n"
        "Criterion 1 (Empirical Support): Idea A = X, Idea B = Y\n"
        "Criterion 2 (Theoretical Coherence): Idea A = X, Idea B = Y\n"
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
    replacement_rate: float = 0.2,  # % of ideas to replace each round
    min_ideas: int = 15,  # Minimum ideas to maintain
    max_ideas: int = 30,  # Maximum total ideas allowed
    num_final_ideas: int = 5,  # Number of ideas to include in final report
    output_dir: Optional[str] = None  # Directory for output files and logs
) -> None:
    """
    Streamlined workflow with integrated tournament and evolution cycles:
    1. For each round:
       a. Generate/evolve ideas based on previous tournament results
       b. Evaluate ideas against scientific criteria
       c. Run tournament to rank ideas and calculate ELO scores
       d. Generate round summary
    2. After all rounds, create final reports with meta-review of top ideas

    Args:
        research_goal: The research question or goal to explore
        num_initial_ideas: Number of ideas to generate in first round (controlled by --initial-ideas)
        num_rounds: Number of evolution rounds to run
        replacement_rate: Percentage of bottom-performing ideas to replace each round
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
            # Use specified output directory directly
            scientia_dir = output_dir
            if not os.path.exists(scientia_dir):
                os.makedirs(scientia_dir)
            print(f"Using specified directory: {scientia_dir} for output\n")
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
        f"Then, outline the streamlined workflow we'll follow:\n"
        f"1. We will conduct {num_rounds} rounds of integrated idea evolution and tournament cycles\n"
        f"2. Each round will include idea generation/evolution, evaluation, and tournament ranking\n"
        f"3. Each iteration, bottom-performing ideas will be replaced with new ones\n"
        f"4. Each idea will maintain an explicit hypothesis with relevant citations using [Author Year] format\n"
        f"5. After all rounds, we'll select the top-ranked ideas for final reporting\n\n"
        f"Keep your introduction focused specifically on this research goal and provide a clear roadmap "
        f"for the agents involved in each phase of the process."
    )

    print("Initializing supervisor agent...")
    supervisor_intro = call_agent(
        get_supervisor_agent_prompt(),
        user_prompt=user_prompt,
        agent_name="supervisor"
    )
    print(supervisor_intro)
    print("")

    # Initialize idea evolution tracker
    idea_tracker = IdeaEvolution()

    # Track current round's ideas for tournament
    current_ideas: Dict[int, str] = {}
    ideas: List[str] = []

    # Initialize tournament_results as empty for the first round
    tournament_results = []

    for round_idx in range(num_rounds):
        print(f"\n========== ROUND {round_idx+1} / {num_rounds} ==========\n")

        # Summarize all current ideas and their ELO scores if not the first round
        if round_idx > 0 and current_ideas:
            print("\n=== CURRENT IDEAS SUMMARY ===\n")
            print(f"Total ideas: {len(current_ideas)}\n")

            # Create a list of (idea_id, elo_score) tuples for sorting
            idea_elo_pairs = []
            for idea_id in current_ideas.keys():
                metadata = idea_tracker.get_metadata(idea_id)
                current_elo = metadata.elo_history[-1] if metadata.elo_history else 1200.0
                idea_elo_pairs.append((idea_id, current_elo))

            # Sort by ELO score in descending order
            idea_elo_pairs.sort(key=lambda x: x[1], reverse=True)

            # Print the sorted ideas with their ELO scores
            print("ID  | ELO Score | Title")
            print("----|-----------|------------------------------------------------------")
            for rank, (idea_id, elo) in enumerate(idea_elo_pairs, 1):
                # Extract title from idea text
                idea_text = current_ideas[idea_id]
                sections = parse_structured_idea(idea_text)
                title = sections.get("title", "Untitled Idea")
                
                # Ensure title is valid and meaningful 
                if not title or title.lower().startswith("key references") or title.lower().startswith("paragraph"):
                    # Try to use the first meaningful part of the idea to create a title
                    if sections.get("key_idea"):
                        first_sentence = re.split(r'[.!?]', sections["key_idea"])[0].strip()
                        if len(first_sentence) < 50:
                            title = first_sentence
                        else:
                            title = sections["key_idea"][:47] + "..."
                    else:
                        title = "Untitled Idea"
                
                # Truncate title if too long
                if len(title) > 50:
                    title = title[:47] + "..."

                print(f"{idea_id:3d} | {elo:9.1f} | {title}")

            print("\n")

        # A. Idea Generation/Evolution Phase
        if round_idx == 0:
            # First round: Generate initial ideas based on user-specified count
            print("\n=== INITIAL IDEA GENERATION ===\n")
            # Use the requested number of initial ideas without artificial cap
            actual_initial_ideas = num_initial_ideas
            
            gen_prompt = (
                f"Please generate EXACTLY {actual_initial_ideas} HIGHLY DIVERSE and distinct research ideas or hypotheses "
                f"for the goal: '{research_goal}'. I need precisely {actual_initial_ideas} ideas - no more, no less. "
                f"Each idea MUST have a UNIQUE, SPECIFIC TITLE that clearly identifies its core concept. "
                f"Titles should be 5-10 words, noun phrases (not sentences), and must not start with phrases like "
                f"'A Study of' or 'Investigation into'. Make each title distinctive and memorable.\n\n"
                f"Maximize diversity across theoretical approaches, methodologies, scales of analysis, and disciplinary perspectives. "
                f"Ensure that each idea explores a fundamentally different angle or mechanism. For each idea, include an explicit "
                f"hypothesis with relevant citations using the format [Author Year]. "
                f"Include citations to support the hypothesis statement and problem description where possible. "
                f"Focus on making each idea as different as possible from the others to ensure broad coverage of the solution space.\n\n"
                f"Title Guidelines:\n"
                f"- Each title MUST be completely unique and different from all others\n"
                f"- Titles should specifically identify the core hypothesis or mechanism\n"
                f"- Titles should NOT include methodology details (like 'Using Machine Learning')\n"
                f"- Titles should NOT start with 'The', 'A', 'An', 'We will', or similar\n"
                f"- Bad title example: 'The Investigation of FDXR Response to Radiation'\n"
                f"- Good title example: 'FDXR Epigenetic Modifications in Radiation Response'\n\n"
                f"IMPORTANT: You MUST generate EXACTLY {actual_initial_ideas} ideas - each with all required sections and a proper unique title."
            )
            generation_output = call_agent(
                get_generation_agent_prompt(),
                user_prompt=gen_prompt,
                agent_name="generation"
            )
            initial_ideas = parse_ideas_from_text(generation_output, expected_count=actual_initial_ideas)

            # Process initial ideas with evaluations
            idea_evaluations = {}  # Store evaluations for each idea
            
            print(f"\n=== DISPLAYING ALL {len(initial_ideas)} GENERATED IDEAS ===\n")
            for i, idea_text in enumerate(initial_ideas):
                # Display the full idea text to the console
                print(f"\n---------- IDEA {i+1}/{len(initial_ideas)} ----------")
                print(idea_text)
                print("------------------------------------------\n")
            
            print("\n=== PROCESSING AND EVALUATING IDEAS ===\n")

            for i, idea_text in enumerate(initial_ideas):
                print(f"\nProcessing initial idea {i+1}/{len(initial_ideas)}...")

                # Add to tracker and get metadata
                idea_id = idea_tracker.add_initial_idea(idea_text)
                current_ideas[idea_id] = idea_text
                idea_metadata = idea_tracker.get_metadata(idea_id)
                unique_id = idea_metadata.unique_id

                # Evaluate against scientific criteria
                print(f"Evaluating idea {idea_id} against scientific criteria...")
                criteria_scores, evaluation_text = evaluate_idea_with_criteria(
                    idea_text,
                    research_goal,
                    get_tournament_agent_prompt()
                )

                # Update metadata with criteria scores
                idea_tracker.update_criteria_scores(idea_id, criteria_scores)

                # Store evaluation for logging
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

            print("=== INITIAL GENERATION COMPLETE ===")
            print("")
        else:
            # Subsequent rounds: Evolve and replace ideas based on tournament results
            print(f"\n=== EVOLUTION PHASE - ROUND {round_idx+1} ===\n")

            # Sort ideas by ELO rating from previous tournament
            sorted_ideas = []
            idea_elo_map = {}

            # Create mapping of idea text to its ELO score and ID
            for i, (idea_text, elo) in enumerate(tournament_results):
                # Find the corresponding idea ID
                idea_id = None
                for id, text in current_ideas.items():
                    if text == idea_text:
                        idea_id = id
                        break
                if idea_id:
                    idea_elo_map[idea_text] = {"elo": elo, "id": idea_id, "rank": i+1}
                    sorted_ideas.append(idea_text)

            # Calculate how many ideas to keep and how many to replace
            # Calculate how many to replace (at least 1 unless we hit max_ideas)
            ideas_count = len(current_ideas)
            keep_count = max(min_ideas, int(ideas_count * (1.0 - replacement_rate)))
            replace_count = ideas_count - keep_count

            # Ensure we're replacing at least one idea (unless at max capacity)
            if replace_count < 1 and ideas_count < max_ideas:
                replace_count = 1
                keep_count = ideas_count - replace_count

            # If we're at max capacity, don't replace any
            if ideas_count >= max_ideas:
                replace_count = 0
                keep_count = ideas_count

            print(f"Evolution strategy: Keep top {keep_count} ideas, replace bottom {replace_count} ideas")

            # Select ideas to keep and to replace
            ideas_to_keep = sorted_ideas[:keep_count]
            ideas_to_replace = sorted_ideas[keep_count:]

            # Prepare evolution prompt with ideas to keep and their feedback
            ideas_text = ""
            for idea_text in ideas_to_keep:
                # Find the idea's ID
                idea_id = idea_elo_map[idea_text]["id"]
                rank = idea_elo_map[idea_text]["rank"]
                elo = idea_elo_map[idea_text]["elo"]

                ideas_text += f"Idea {idea_id} (Rank: {rank}, ELO: {elo:.1f}):\n{idea_text}\n\n"

                # Add reflection feedback for this idea if available
                idea_specific_feedback = extract_idea_specific_feedback(reflection_output, idea_id, len(current_ideas), idea_text)
                if idea_specific_feedback:
                    ideas_text += f"REFLECTION FEEDBACK FOR IDEA {idea_id}:\n{idea_specific_feedback}\n\n"

                ideas_text += "---\n\n"  # Separator between ideas

            # Calculate space for new ideas with a cap of 20 maximum new ideas per round
            space_for_new = min(
                replace_count,
                max_ideas - keep_count,
                20  # Maximum number of new ideas per round
            )

            evolve_prompt = (
                f"We have the following {keep_count} ideas with their rankings and feedback:\n\n"
                f"{ideas_text}\n\n"
                f"1. Please refine and strengthen each existing idea using the feedback and tournament rankings.\n"
                f"2. If rankings or feedback suggest a SIGNIFICANT change to an idea's core premise or approach, create it as a new idea rather than a refinement.\n"
                f"3. Ensure each idea has a PROPER UNIQUE TITLE that clearly identifies its core concept.\n\n"
                f"Title Guidelines:\n"
                f"- Each title MUST be completely unique and different from all others\n"
                f"- Titles should be 5-10 words, noun phrases (not sentences)\n"
                f"- Titles should specifically identify the core hypothesis or mechanism\n"
                f"- Titles should NOT include methodology details (like 'Using Machine Learning')\n"
                f"- Titles should NOT start with 'The', 'A', 'An', 'We will', or similar\n"
                f"- Bad title example: 'The Investigation of FDXR Response to Radiation'\n"
                f"- Good title example: 'FDXR Epigenetic Modifications in Radiation Response'\n"
            )

            if space_for_new > 0:
                evolve_prompt += (
                    f"4. Additionally, generate {space_for_new} HIGHLY DIVERSE NEW ideas to replace the lowest-ranked ideas. "
                    f"These new ideas MUST explore novel angles not covered by the existing ideas. "
                    f"Maximize diversity across theoretical approaches, methodologies, scales of analysis, and disciplinary perspectives. "
                    f"Each new idea should be fundamentally different from all existing ideas AND from each other. "
                    f"Focus especially on exploring completely orthogonal approaches to the research problem.\n\n"
                    f"5. ALL new ideas must have proper unique titles following the guidelines above.\n\n"
                    f"Note: Your new ideas will compete with the refined versions of existing ideas in the next tournament round."
                )
            else:
                evolve_prompt += (
                    f"4. Focus solely on refining existing ideas as we've reached the maximum allowed idea count.\n\n"
                    f"5. Remember to ensure ALL ideas have proper unique titles following the guidelines above."
                )

            # Get the evolution output from the agent
            evolution_output = call_agent(
                get_evolution_agent_prompt(),
                user_prompt=evolve_prompt,
                agent_name="evolution"
            )

            # Parse evolved ideas and potential new ideas
            print("Parsing evolution output...")
            all_evolved_ideas = parse_ideas_from_text(
                evolution_output,
                expected_count=keep_count + space_for_new
            )
            
            # Display all ideas
            print(f"\n=== DISPLAYING ALL {len(all_evolved_ideas)} EVOLVED/NEW IDEAS ===\n")
            for i, idea_text in enumerate(all_evolved_ideas):
                # Display the full idea text to the console
                print(f"\n---------- IDEA {i+1}/{len(all_evolved_ideas)} ----------")
                print(idea_text)
                print("------------------------------------------\n")
            
            print("\n=== PROCESSING EVOLVED/NEW IDEAS ===\n")

            # Split into refined and new ideas
            refined_ideas = all_evolved_ideas[:keep_count]
            new_ideas = all_evolved_ideas[keep_count:]

            # Clear current ideas and rebuild with refined and new ones
            current_ideas.clear()

            # Process refined ideas
            for idx, refined_text in enumerate(refined_ideas):
                if idx < len(ideas_to_keep):
                    # Find the original ID for this idea
                    original_idea = ideas_to_keep[idx]
                    original_id = idea_elo_map[original_idea]["id"]

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
                            original_idea_text = idea_tracker.ideas.get(original_id, "Original idea not found")

                            # Format the evaluation as markdown
                            if is_significant:
                                formatted_evaluation = f"## New Idea from Significant Change (Round {round_idx+1})\n\n"
                                formatted_evaluation += f"This idea represents a significant change from Idea {original_id}.\n\n"
                            else:
                                formatted_evaluation = f"## Refined Idea (Round {round_idx+1})\n\n"

                            formatted_evaluation += f"{refined_text}\n\n"

                            # Show comparison with original
                            formatted_evaluation += f"## Comparison with Original\n\n"
                            formatted_evaluation += f"### Original Idea (ID: {original_id})\n\n{original_idea_text}\n\n"

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

            print("=== EVOLUTION COMPLETE ===")
            print(evolution_output)
            print("")

            # Update ideas list for compatibility with the rest of the code
            ideas = list(current_ideas.values())

        # B. Evaluation Phase
        print("\n=== EVALUATION PHASE ===\n")

        # B.1. Reflection Analysis
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
        print("=== REFLECTION ANALYSIS ===")
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

        # B.2. Proximity Check
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
        print("=== PROXIMITY CHECK ===")
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

        # C. Integrated Tournament
        print("\n=== TOURNAMENT PHASE - ROUND {round_idx+1} ===\n")
        print(f"Running tournament with {len(ideas)} ideas...")

        # Run tournament with all current ideas
        tournament_results = run_optimized_tournament(
            ideas,
            get_tournament_agent_prompt(),
            scientia_dir=scientia_dir,
            idea_tracker=idea_tracker
        )

        # Display tournament results
        print("\n=== TOURNAMENT RESULTS ===")
        print("-" * 80)
        for i, (idea, rating) in enumerate(tournament_results, 1):
            print(f"\n{i}. Final ELO Rating: {rating:.1f}")
            # Extract the title and key idea for display
            sections = parse_structured_idea(idea)
            title = sections.get("title", "")
            key_idea = sections.get("key_idea", "")
            paragraph_1 = sections.get("paragraph_1", "")
            
            # Extensive title validation and cleanup
            invalid_title_indicators = [
                "key references", "paragraph", 
                "approach", "we will use", 
                ", we will", "this idea performs",
                "**", "3**:", "2**:", "1**:"
            ]
            
            title_is_valid = title and not any(title.lower().startswith(indicator) or 
                                           indicator in title.lower() for indicator in invalid_title_indicators)
            
            # If the title is not valid, create a good one
            if not title_is_valid:
                # First try using the key idea
                if key_idea:
                    # Remove anything after the first sentence
                    first_sentence = re.split(r'[.!?]', key_idea)[0].strip()
                    # Ensure it's not too long
                    if len(first_sentence) < 60 and not any(indicator in first_sentence.lower() 
                                                         for indicator in invalid_title_indicators):
                        title = first_sentence
                    else:
                        # Use first 57 chars of key idea if sentence is too long
                        title = key_idea[:57] + "..."
                # If no good key idea, try first paragraph
                elif paragraph_1:
                    first_sentence = re.split(r'[.!?]', paragraph_1)[0].strip()
                    if len(first_sentence) < 60:
                        title = first_sentence
                    else:
                        title = paragraph_1[:57] + "..."
                else:
                    # Last resort
                    title = f"Research Idea #{i}"
            
            # Final check for any remaining issues (titles starting with commas, etc.)
            if title.startswith(",") or title.startswith("to ") or title.startswith("es "):
                # Clean up by removing the prefix
                title = re.sub(r'^[,\s]+(to |es )?', '', title)
                
            # If still empty or invalid, use a generic title
            if not title or len(title) < 5:
                title = f"Research Idea #{i}"
            
            # Truncate title if too long
            if len(title) > 60:
                title = title[:57] + "..."
                
            print(f"Title: {title}")
            print("Key Idea:")
            print(textwrap.fill(key_idea or idea[:200] + "...", width=80, initial_indent="  ", subsequent_indent="  "))
        print("-" * 80)

        # Log tournament results for each idea
        if scientia_dir:
            try:
                for i, (idea, rating) in enumerate(tournament_results, 1):
                    # Find the idea's ID
                    idea_id = None
                    for id, text in current_ideas.items():
                        if text == idea:
                            idea_id = id
                            break

                    if idea_id:
                        # Get metadata for this idea
                        idea_metadata = idea_tracker.get_metadata(idea_id)
                        idea_unique_id = idea_metadata.unique_id

                        # Format the tournament result as markdown
                        tournament_entry = f"## Tournament Results (Round {round_idx+1})\n\n"
                        tournament_entry += f"**Rank:** {i} out of {len(tournament_results)}\n"
                        tournament_entry += f"**ELO Rating:** {rating:.1f}\n\n"
                        tournament_entry += f"### Idea\n\n{idea}\n\n"

                        # Log to idea-specific file
                        log_idea(
                            scientia_dir,
                            idea_id,
                            tournament_entry,
                            f"Tournament Round {round_idx+1}",
                            round_idx+1,
                            elo_score=rating,
                            unique_id=idea_unique_id,
                            metadata=idea_metadata
                        )
            except Exception as e:
                print(f"Warning: Failed to log tournament results: {e}")

        # D. Round Summary
        # First, prepare a clean list of ideas with proper titles
        idea_summaries = []
        for i, (idea, rating) in enumerate(tournament_results):
            sections = parse_structured_idea(idea)
            title = sections.get("title", "Untitled Idea")
            
            # Clean title
            if not title or title.lower().startswith("key references") or title.lower().startswith("paragraph"):
                if sections.get("key_idea"):
                    first_sentence = re.split(r'[.!?]', sections["key_idea"])[0].strip()
                    if len(first_sentence) < 50:
                        title = first_sentence
                    else:
                        title = sections["key_idea"][:47] + "..."
                else:
                    title = "Untitled Idea"
            
            # Truncate title if too long
            if len(title) > 50:
                title = title[:47] + "..."
                
            idea_summaries.append(f"{i+1}. ELO: {rating:.1f} - {title}")
        
        supervisor_prompt = (
            f"Summarize the results of round {round_idx+1} of our integrated idea evolution and tournament process.\n\n"
            f"TOURNAMENT RESULTS:\n"
            + "\n".join(idea_summaries)
            + "\n\n"
            f"REFLECTION OUTPUT:\n{reflection_output}\n\n"
            f"PROXIMITY CHECK OUTPUT:\n{proximity_output}\n\n"
            f"Based on these outputs, summarize:\n"
            f"1. The current state of the top ideas\n"
            f"2. Key improvements made this round\n"
            f"3. Emerging patterns or trends\n"
            f"4. Recommendations for the next round\n"
        )

        # Get round summary from supervisor agent
        round_summary = call_agent(
            get_supervisor_agent_prompt(),
            user_prompt=supervisor_prompt,
            agent_name="supervisor"
        )
        print("\n=== ROUND SUMMARY ===")
        print(round_summary)
        print("")

        # Log the supervisor's summary
        if scientia_dir:
            try:
                # Create a summary file for this round
                round_summary_file = os.path.join(scientia_dir, f"round_{round_idx+1}_summary.md")
                with open(round_summary_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Round {round_idx+1} Summary\n\n")
                    f.write(round_summary)
                    f.write("\n\n## Tournament Rankings\n\n")
                    f.write("| Rank | Title | ELO Rating |\n|---:|---|---:|\n")

                    for i, (idea, rating) in enumerate(tournament_results, 1):
                        sections = parse_structured_idea(idea)
                        title = sections.get("title", "Untitled")
                        f.write(f"| {i} | {title} | {rating:.1f} |\n")

                # Also log round summary for each idea
                for i, idea in enumerate(ideas):
                    summary_entry = f"{idea}\n\n--- ROUND {round_idx+1} SUMMARY ---\n\n{round_summary}"
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

    # Final output generation
    print("\n========== FINAL OUTPUT GENERATION ==========\n")
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
                    # Get title for display
                    sections = parse_structured_idea(idea)
                    title = sections.get("title", "Untitled")
                    
                    f.write(f"### {i}. {title} (ELO: {rating:.1f})\n\n")
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
                    top_title = top_sections.get("title", "")
                    top_key_idea = top_sections.get("key_idea", "")
                    top_paragraph_1 = top_sections.get("paragraph_1", "")
                    
                    # Extensive title validation and cleanup
                    invalid_title_indicators = [
                        "key references", "paragraph", 
                        "approach", "we will use", 
                        ", we will", "this idea performs",
                        "**", "3**:", "2**:", "1**:"
                    ]
                    
                    title_is_valid = top_title and not any(top_title.lower().startswith(indicator) or 
                                                  indicator in top_title.lower() for indicator in invalid_title_indicators)
                    
                    # If the title is not valid, create a good one
                    if not title_is_valid:
                        # First try using the key idea
                        if top_key_idea:
                            # Remove anything after the first sentence
                            first_sentence = re.split(r'[.!?]', top_key_idea)[0].strip()
                            # Ensure it's not too long
                            if len(first_sentence) < 50 and not any(indicator in first_sentence.lower() 
                                                                 for indicator in invalid_title_indicators):
                                top_title = first_sentence
                            else:
                                # Use first 47 chars of key idea if sentence is too long
                                top_title = top_key_idea[:47] + "..."
                        # If no good key idea, try first paragraph
                        elif top_paragraph_1:
                            first_sentence = re.split(r'[.!?]', top_paragraph_1)[0].strip()
                            if len(first_sentence) < 50:
                                top_title = first_sentence
                            else:
                                top_title = top_paragraph_1[:47] + "..."
                        else:
                            # Last resort
                            top_title = f"Research Idea #{j+1}"
                    
                    # Final check for any remaining issues (titles starting with commas, etc.)
                    if top_title.startswith(",") or top_title.startswith("to ") or top_title.startswith("es "):
                        # Clean up by removing the prefix
                        top_title = re.sub(r'^[,\s]+(to |es )?', '', top_title)
                        
                    # If still empty or invalid, use a generic title
                    if not top_title or len(top_title) < 5:
                        top_title = f"Research Idea #{j+1}"
                    
                    display_title = top_title[:50] + ("..." if len(top_title) > 50 else "")
                    
                    if top_idea == idea:
                        meta_entry += f"| **{j+1}** | **This idea** | **{top_rating:.1f}** |\n"
                    else:
                        meta_entry += f"| {j+1} | {display_title} | {top_rating:.1f} |\n"
                
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
    # Generate comprehensive final reports for ALL ideas that have been generated
    if scientia_dir:
        try:
            print("\nGenerating comprehensive final reports for ALL ideas...")
            
            # Get all ideas from the tracker
            all_ideas = idea_tracker.get_all_ideas()
            print(f"Found {len(all_ideas)} total ideas in tracker")
            
            # First, create a mapping of idea texts to ELO ratings from tournament results
            idea_ratings = {idea: rating for idea, rating in tournament_results}
            
            # Process each idea in the tracker
            for idea_id, idea_text in all_ideas.items():
                # Get the latest ELO rating from the idea's metadata
                idea_metadata = idea_tracker.get_metadata(idea_id)
                
                # Check if the idea has a history of ELO ratings
                if idea_metadata and idea_metadata.elo_history and len(idea_metadata.elo_history) > 0:
                    # Use the last (most recent) ELO rating
                    rating = idea_metadata.elo_history[-1]
                    print(f"Using tracked ELO rating for idea {idea_id}: {rating:.1f}")
                else:
                    # If there's no ELO history, try to get it from tournament results
                    rating = idea_ratings.get(idea_text, 1200.0)
                    print(f"Using tournament ELO rating for idea {idea_id}: {rating:.1f}")
                
                log_file_path = os.path.join(scientia_dir, f"idea_{idea_id}.log")
                if os.path.exists(log_file_path):
                    try:
                        generate_final_report(scientia_dir, idea_id, idea_text, rating, log_file_path, idea_tracker)
                        print(f"Generated final report for idea {idea_id}")
                    except Exception as e:
                        print(f"Error generating report for idea {idea_id}: {e}")
                        traceback.print_exc()
                else:
                    print(f"Warning: Log file not found for idea {idea_id}")
            
            print(f"\nAll final reports saved to: {scientia_dir}")
            
            # Create a summary file with links to ALL idea reports
            summary_file = os.path.join(scientia_dir, "summary.md")
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"# Research Summary: {problem_name}\n\n")
                f.write(f"## Research Goal\n\n{research_goal}\n\n")
                f.write("## Top Ideas Ranked by ELO Rating\n\n")
                
                # Create a list of all ideas with their current ELO ratings from the tracker
                all_ideas_with_elo = []
                for idea_id, idea_text in idea_tracker.get_all_ideas().items():
                    metadata = idea_tracker.get_metadata(idea_id)
                    # Use the latest ELO rating from the idea's history
                    if metadata.elo_history and len(metadata.elo_history) > 0:
                        current_elo = metadata.elo_history[-1]
                        all_ideas_with_elo.append((idea_text, current_elo, idea_id))
                        
                print("\n=== SORTING IDEAS BY CURRENT ELO RATINGS ===")
                print(f"Found {len(all_ideas_with_elo)} ideas with ELO ratings")
                
                # Sort by ELO rating in descending order
                all_ideas_with_elo.sort(key=lambda x: x[1], reverse=True)
                
                # Debug output to show top 10 ELO ratings with full details
                print("\n=== TOP 10 IDEAS BY ELO RATING (DEBUGGING) ===")
                for j, (idea, elo, id) in enumerate(all_ideas_with_elo[:10], 1):
                    # Get title for better identification
                    s = parse_structured_idea(idea)
                    t = s.get("title", "")[:30]
                    # Print full details for debugging
                    print(f"{j}. Idea {id}: ELO {elo:.1f} - Title: {t}")
                
                # Verify the sorting is correct by checking if ratings are decreasing
                is_sorted = all(all_ideas_with_elo[i][1] >= all_ideas_with_elo[i+1][1] for i in range(min(9, len(all_ideas_with_elo)-1)))
                print(f"\nVerification - Ideas properly sorted by ELO: {'YES' if is_sorted else 'NO - ERROR!'}")
                
                # Select top ideas by actual ELO rating
                for i, (idea, rating, idea_num) in enumerate(all_ideas_with_elo[:num_final_ideas], 1):
                    
                    # Get title for better display
                    sections = parse_structured_idea(idea)
                    title = sections.get("title", "")
                    key_idea = sections.get("key_idea", "")
                    paragraph_1 = sections.get("paragraph_1", "")
                    
                    # Extensive title validation and cleanup
                    invalid_title_indicators = [
                        "key references", "paragraph", 
                        "approach", "we will use", 
                        ", we will", "this idea performs",
                        "**", "3**:", "2**:", "1**:"
                    ]
                    
                    title_is_valid = title and not any(title.lower().startswith(indicator) or 
                                                   indicator in title.lower() for indicator in invalid_title_indicators)
                    
                    # If the title is not valid, create a good one
                    if not title_is_valid:
                        # First try using the key idea
                        if key_idea:
                            # Remove anything after the first sentence
                            first_sentence = re.split(r'[.!?]', key_idea)[0].strip()
                            # Ensure it's not too long
                            if len(first_sentence) < 80 and not any(indicator in first_sentence.lower() 
                                                                 for indicator in invalid_title_indicators):
                                title = first_sentence
                            else:
                                # Use first 77 chars of key idea if sentence is too long
                                title = key_idea[:77] + "..."
                        # If no good key idea, try first paragraph
                        elif paragraph_1:
                            first_sentence = re.split(r'[.!?]', paragraph_1)[0].strip()
                            if len(first_sentence) < 80:
                                title = first_sentence
                            else:
                                title = paragraph_1[:77] + "..."
                        else:
                            # Last resort
                            title = f"Research Idea #{idea_num}"
                    
                    # Final check for any remaining issues (titles starting with commas, etc.)
                    if title.startswith(",") or title.startswith("to ") or title.startswith("es "):
                        # Clean up by removing the prefix
                        title = re.sub(r'^[,\s]+(to |es )?', '', title)
                        
                    # If still empty or invalid, use a generic title
                    if not title or len(title) < 5:
                        title = f"Research Idea #{idea_num}"
                    
                    display_title = title[:80] + ("..." if len(title) > 80 else "")
                    
                    # Don't overwrite the rating that was already retrieved and sorted
                    # The rating already contains the correct ELO value from all_ideas_with_elo
                    # The code below was causing all ideas to use the same rating
                    
                    # Debug output to verify the actual rating being used
                    print(f"Using ELO rating for idea {idea_num}: {rating:.1f}")
                    
                    # Get a clean key idea summary
                    key_idea = sections.get('key_idea', idea[:100])
                    if key_idea:
                        key_idea_summary = key_idea[:200] + ("..." if len(key_idea) > 200 else "")
                    else:
                        key_idea_summary = idea[:100] + "..."
                    
                    f.write(f"{i}. **[{display_title}](idea_{idea_num}_final.md)** - ELO: {rating:.1f}\n\n")
                    f.write(f"   {key_idea_summary}\n\n")
                
                f.write("\n## All Generated Ideas\n\n")
                f.write("| ID | Title | ELO | Type | Parent |\n")
                f.write("|---:|---|---:|---|---:|\n")
                
                # Then list ALL ideas in ID order
                sorted_idea_ids = sorted(list(all_ideas.keys()))
                for idea_id in sorted_idea_ids:
                    idea_text = all_ideas[idea_id]
                    metadata = idea_tracker.get_metadata(idea_id)
                    
                    # Extract info for display
                    sections = parse_structured_idea(idea_text)
                    title = sections.get("title", "")
                    key_idea = sections.get("key_idea", "")
                    paragraph_1 = sections.get("paragraph_1", "")
                    
                    # Extensive title validation and cleanup
                    invalid_title_indicators = [
                        "key references", "paragraph", 
                        "approach", "we will use", 
                        ", we will", "this idea performs",
                        "**", "3**:", "2**:", "1**:"
                    ]
                    
                    title_is_valid = title and not any(title.lower().startswith(indicator) or 
                                                   indicator in title.lower() for indicator in invalid_title_indicators)
                    
                    # If the title is not valid, create a good one
                    if not title_is_valid:
                        # First try using the key idea
                        if key_idea:
                            # Remove anything after the first sentence
                            first_sentence = re.split(r'[.!?]', key_idea)[0].strip()
                            # Ensure it's not too long
                            if len(first_sentence) < 50 and not any(indicator in first_sentence.lower() 
                                                                  for indicator in invalid_title_indicators):
                                title = first_sentence
                            else:
                                # Use first 47 chars of key idea if sentence is too long
                                title = key_idea[:47] + "..."
                        # If no good key idea, try first paragraph
                        elif paragraph_1:
                            first_sentence = re.split(r'[.!?]', paragraph_1)[0].strip()
                            if len(first_sentence) < 50:
                                title = first_sentence
                            else:
                                title = paragraph_1[:47] + "..."
                        else:
                            # Last resort
                            title = f"Research Idea #{idea_id}"
                    
                    # Final check for any remaining issues (titles starting with commas, etc.)
                    if title.startswith(",") or title.startswith("to ") or title.startswith("es "):
                        # Clean up by removing the prefix
                        title = re.sub(r'^[,\s]+(to |es )?', '', title)
                        
                    # If still empty or invalid, use a generic title
                    if not title or len(title) < 5:
                        title = f"Research Idea #{idea_id}"
                    
                    display_title = title[:50] + ("..." if len(title) > 50 else "")
                    
                    # Get the most recent ELO rating from the idea's history or tournament results
                    if metadata and metadata.elo_history and len(metadata.elo_history) > 0:
                        rating = metadata.elo_history[-1]
                    else:
                        rating = idea_ratings.get(idea_text, 1200.0)
                        
                    gen_type = getattr(metadata, "generation_type", "Unknown")
                    parent_id = getattr(metadata, "parent_id", "-")
                    
                    f.write(f"| {idea_id} | [{display_title}](idea_{idea_id}_final.md) | {rating:.1f} | {gen_type} | {parent_id} |\n")
                
                f.write("\n## Meta-Review\n\n")
                f.write("See the [full meta-review](meta_review.md) for detailed analysis of the top ideas.\n")
            
            print(f"Summary document created: {summary_file}")
        except Exception as e:
            print(f"Warning: Error generating final reports: {e}")
            traceback.print_exc()
    
def compute_idea_score_vectors(ideas: List[str], tournament_agent_prompt: str) -> Dict[str, IdeaScore]:
    """
    Compute score vectors for ideas in a single batch of calls to reduce API usage.
    
    Args:
        ideas: List of ideas to score
        tournament_agent_prompt: Prompt for the tournament agent
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

# Main tournament optimization function
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

def run_optimized_tournament(
    ideas: List[str],
    tournament_agent_prompt: str,
    num_opponents: int = 10,
    scientia_dir: Optional[str] = None,
    only_update_ideas: Optional[List[str]] = None,
    idea_tracker: Optional[IdeaEvolution] = None  # Add idea_tracker parameter
) -> List[Tuple[str, float]]:
    """
    Run an optimized tournament using pre-computed score vectors and batched ELO updates.
    
    Args:
        ideas: List of ideas to compare
        tournament_agent_prompt: Prompt for the tournament agent
        num_opponents: Number of random opponents for each idea
        scientia_dir: Optional directory for logging
        
    Returns:
        List of (idea, final_elo_rating) tuples sorted by rating
#    """
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
    
    # Compute or reuse score vectors
    global idea_score_vectors  # Store vectors globally for reuse across rounds
    
    # Initialize global score vector dictionary if not exists
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
                    print(f"Using stored criteria scores for idea starting with: {idea[:50]}...")
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
    
    # Initialize ELO ratings - check if idea_tracker has existing ratings
    elo_ratings = {}
    total_existing_ideas = 0
    
    print("\n=== INITIALIZING ELO RATINGS ===")
    
    # First pass - find existing ratings
    for idea in ideas:
        # Try to find existing rating in idea_tracker
        existing_rating = None
        existing_id = None
        if idea_tracker:
            for id, text in idea_tracker.get_all_ideas().items():
                if text == idea:
                    metadata = idea_tracker.get_metadata(id)
                    if metadata.elo_history and len(metadata.elo_history) > 0:
                        existing_rating = metadata.elo_history[-1]
                        existing_id = id
                        total_existing_ideas += 1
                        break
        
        # Store the rating and ID for later use
        if existing_rating is not None:
            elo_ratings[idea] = existing_rating
            print(f"Using existing rating for idea {existing_id}: {existing_rating:.1f}")
        else:
            # Default to a range around 1200 to create initial separation
            # This helps avoid starting with identical ratings
            elo_ratings[idea] = 1200.0
            
    # Second pass - if this is a subsequent round, initialize new ideas with 
    # meaningful starting values to avoid all ideas having the same rating
    if total_existing_ideas > 0 and total_existing_ideas < len(ideas):
        # Get the average and std dev of existing ratings
        existing_ratings = [rating for rating in elo_ratings.values() if rating != 1200.0]
        avg_rating = sum(existing_ratings) / len(existing_ratings)
        
        # Initialize new ideas with a slight distribution around the average
        for idea in ideas:
            if elo_ratings[idea] == 1200.0:  # This is a new idea without existing rating
                # Give new ideas a small random offset to create initial separation
                # but keep them close to the average so they're neither too advantaged nor disadvantaged
                offset = random.uniform(-50, 50)  # Random offset between -50 and +50
                elo_ratings[idea] = avg_rating + offset
                print(f"New idea initialized with rating: {elo_ratings[idea]:.1f}")
    elif total_existing_ideas == 0:
        # If all ideas are new, create a small initial spread for better differentiation
        for idea in ideas:
            # Random offset between -25 and +25 from default 1200
            offset = random.uniform(-25, 25)
            elo_ratings[idea] = 1200.0 + offset
            print(f"New idea initialized with rating: {elo_ratings[idea]:.1f}")
    
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
            # Log the match details
            print(f"Vector-based comparison score: {match_score:.3f}")
            print("\nPre-computed scores by criterion:")
            
            # Print scores for each criterion using the global TOURNAMENT_CRITERIA constant
            for c_idx, (criterion, a_score, b_score) in enumerate(zip(TOURNAMENT_CRITERIA, list(vec_a), list(vec_b))):
                print(f"  {criterion}: A={a_score:.1f}, B={b_score:.1f}")
    # Process all ELO updates in batches
    print("\n=== PROCESSING BATCHED ELO UPDATES ===")
    batch_size = 50  # Process ELO updates in batches of 50 matches
    
    # Track all ideas and their performance stats to help with analyzing rating adjustments
    match_stats: Dict[str, Dict[str, Any]] = {}
    for idea in ideas:
        match_stats[idea] = {
            "matches_played": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "score_sum": 0.0,
            "avg_performance": 0.0,
        }
        
    # Debug output current ELO ratings before tournament
    print("\n=== CURRENT ELO RATINGS BEFORE TOURNAMENT ===")
    for idea in ideas:
        idea_idx = ideas.index(idea) + 1
        print(f"Idea {idea_idx}: {elo_ratings[idea]:.1f}")
    
    # First, calculate all raw ELO updates to get performance statistics
    print("\n=== CALCULATING PERFORMANCE STATISTICS ===")
    raw_rating_changes: Dict[str, List[float]] = {}  # Store all individual changes
    
    for idea_a, idea_b, score in pending_elo_updates:
        # Update match statistics
        match_stats[idea_a]["matches_played"] += 1
        match_stats[idea_b]["matches_played"] += 1
        match_stats[idea_a]["score_sum"] += score
        match_stats[idea_b]["score_sum"] += (1 - score)
        
        if score > 0.5:
            match_stats[idea_a]["wins"] += 1
            match_stats[idea_b]["losses"] += 1
        elif score < 0.5:
            match_stats[idea_a]["losses"] += 1
            match_stats[idea_b]["wins"] += 1
        else:
            match_stats[idea_a]["ties"] += 1
            match_stats[idea_b]["ties"] += 1
        
        # Calculate raw rating changes
        old_rating_a = elo_ratings[idea_a]
        old_rating_b = elo_ratings[idea_b]
        new_rating_a, new_rating_b = calculate_elo_update(old_rating_a, old_rating_b, score)
        
        # Store individual changes
        if idea_a not in raw_rating_changes:
            raw_rating_changes[idea_a] = []
        if idea_b not in raw_rating_changes:
            raw_rating_changes[idea_b] = []
        
        raw_rating_changes[idea_a].append(new_rating_a - old_rating_a)
        raw_rating_changes[idea_b].append(new_rating_b - old_rating_b)
    
    # Calculate average performance for each idea
    for idea in match_stats:
        if match_stats[idea]["matches_played"] > 0:
            match_stats[idea]["avg_performance"] = match_stats[idea]["score_sum"] / match_stats[idea]["matches_played"]
    
    # Apply processed ELO updates in batches
    for i in range(0, len(pending_elo_updates), batch_size):
        batch = pending_elo_updates[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(pending_elo_updates) + batch_size - 1)//batch_size}...")
        
        # Apply accumulated changes for each idea at once
        rating_changes: Dict[str, float] = {}
        
        # Process all unique ideas in this batch
        unique_ideas = set()
        for idea_a, idea_b, _ in batch:
            unique_ideas.add(idea_a)
            unique_ideas.add(idea_b)
        
        # For each idea, calculate the aggregate change
        for idea in unique_ideas:
            # Take the average of all changes for this idea
            changes = raw_rating_changes[idea]
            avg_change = sum(changes) / len(changes)
            
            # Apply changes
            rating_changes[idea] = avg_change
        
        # Print performance summary
        print("\n=== PERFORMANCE SUMMARY ===")
        print(f"{'Idea':6} | {'Matches':8} | {'Win%':6} | {'Draw%':6} | {'Avg Perf':8}")
        print(f"{'-'*6} | {'-'*8} | {'-'*6} | {'-'*6} | {'-'*8}")
        
        for idea in sorted(match_stats.keys(), key=lambda x: match_stats[x]["avg_performance"], reverse=True):
            if match_stats[idea]["matches_played"] > 0:
                idea_idx = ideas.index(idea) + 1
                stats = match_stats[idea]
                win_pct = stats["wins"] / stats["matches_played"] * 100
                draw_pct = stats["ties"] / stats["matches_played"] * 100
                avg_perf = stats["avg_performance"]
                
                print(f"{idea_idx:6} | {stats['matches_played']:8} | {win_pct:5.1f}% | {draw_pct:5.1f}% | {avg_perf:8.3f}")
        
        # Apply accumulated changes
        print("\n=== ELO RATING CHANGES ===")
        print(f"{'Idea':6} | {'Change':10} | {'New ELO':8}")
        print(f"{'-'*6} | {'-'*10} | {'-'*8}")
        
        # Apply changes based on performance - ideas that performed better should gain more
        for idea, change in sorted(rating_changes.items(), key=lambda x: abs(x[1]), reverse=True):
            # Apply scaling factor to ensure differentiation
            # Ideas with extreme performances (much better/worse than 0.5) should see larger changes
            perf_factor = 1.0
            avg_perf = match_stats[idea]["avg_performance"]
            if avg_perf > 0.5:
                perf_factor = 1.0 + (avg_perf - 0.5) * 2  # Up to 2x for perfect performance
            elif avg_perf < 0.5:
                perf_factor = 1.0 + (0.5 - avg_perf) * 2  # Up to 2x for worst performance
            
            # Apply the adjusted change
            adjusted_change = change * perf_factor
            elo_ratings[idea] += adjusted_change
            idea_idx = ideas.index(idea) + 1
            
            # Format with arrow indicating positive/negative change
            direction = "↑" if adjusted_change > 0 else "↓" if adjusted_change < 0 else "="
            print(f"{idea_idx:6} | {direction} {abs(adjusted_change):+7.1f} | {elo_ratings[idea]:8.1f}")

            # Update the ELO score in the idea tracker if available
            if idea_tracker:
                # Find the idea in the tracker
                for id, text in idea_tracker.get_all_ideas().items():
                    if text == idea:
                        # Get current metadata and last ELO
                        metadata = idea_tracker.get_metadata(id)
                        last_elo = metadata.elo_history[-1] if metadata.elo_history and metadata.elo_history else 1200.0
                        new_elo = elo_ratings[idea]
                        
                        # CRITICAL FIX: Ensure we always have at least a minimum change for ideas
                        # that performed well or poorly in tournament
                        min_change_threshold = 5.0  # Increased minimum change amount
                        
                        # Always ensure change for significantly different performances
                        if abs(avg_perf - 0.5) > 0.05:  # Reduced threshold to 5% difference from average
                            # Force minimum change in the appropriate direction
                            direction = 1 if avg_perf > 0.5 else -1
                            
                            # Calculate minimum required change
                            required_change = min_change_threshold * direction
                            
                            # If current change is less than minimum required, use the required change
                            if abs(new_elo - last_elo) < min_change_threshold:
                                new_elo = last_elo + required_change
                                # Update the master dictionary too
                                elo_ratings[idea] = new_elo
                                print(f"Applied minimum change: {required_change:+.1f} to idea with performance deviation: {avg_perf-0.5:+.3f}")
                        
                        # IMPORTANT: Always update ELO for consistency between rounds
                        # Even minor changes should be recorded to prevent reset to 1200
                        if abs(last_elo - new_elo) < 0.01:
                            # If no change, but performance was different from 0.5, force a small change
                            if abs(avg_perf - 0.5) > 0.01:
                                direction = 1 if avg_perf > 0.5 else -1
                                new_elo = last_elo + (0.5 * direction)  # Force at least a 0.5 point change
                                elo_ratings[idea] = new_elo
                                print(f"Forced minimum change to prevent stagnation")
                            
                        # Update ELO history with the finalized value - ALWAYS update to maintain consistency
                        idea_tracker.update_elo(id, new_elo)
                        print(f"Updated ELO for idea {id} from {last_elo:.1f} to {new_elo:.1f}")
                        break
    
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
    
    # Debug output - verify that ELO ratings are different and properly updated
    print("\n=== FINAL ELO RATINGS AFTER TOURNAMENT ===")
    has_differentiation = False
    baseline_rating = None
    
    # Check for differentiation in ratings
    for idea in ideas:
        idea_idx = ideas.index(idea) + 1
        print(f"Idea {idea_idx}: {elo_ratings[idea]:.1f}")
        
        if baseline_rating is None:
            baseline_rating = elo_ratings[idea]
        elif abs(elo_ratings[idea] - baseline_rating) > 1.0:
            has_differentiation = True
    
    if not has_differentiation:
        print("\n⚠️ WARNING: ELO ratings show insufficient differentiation! ⚠️")
        
        # Emergency correction - force differentiation based on avg_performance if needed
        if all(abs(elo_ratings[idea] - 1200.0) < 1.0 for idea in ideas):
            print("\n🔄 Emergency correction: Applying forced differentiation based on tournament performance!")
            
            # Sort ideas by their average performance
            sorted_ideas = sorted(match_stats.keys(), 
                                 key=lambda x: match_stats[x]["avg_performance"], 
                                 reverse=True)
            
            # Apply scaled ELO ratings based on rank
            for rank, idea in enumerate(sorted_ideas):
                # Scale from 1300 (best) down to 1100 (worst)
                scaled_elo = 1300 - (rank * (200 / max(1, len(sorted_ideas) - 1)))
                elo_ratings[idea] = scaled_elo
                
                # Update in the idea tracker
                if idea_tracker:
                    for id, text in idea_tracker.get_all_ideas().items():
                        if text == idea:
                            idea_tracker.update_elo(id, scaled_elo)
                            print(f"Emergency update - Idea {id}: Set ELO to {scaled_elo:.1f} (rank {rank+1})")
                            break
    
    # Return the sorted list of ideas by their final ELO rating
    final_sorted_results = sorted(
        [(idea, rating) for idea, rating in elo_ratings.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Print the final sorted list 
    print("\n=== FINAL TOURNAMENT RANKINGS ===")
    for rank, (idea, rating) in enumerate(final_sorted_results, 1):
        # Extract idea title for better identification
        sections = parse_structured_idea(idea)
        title = sections.get("title", "")
        key_idea = sections.get("key_idea", "")
        paragraph_1 = sections.get("paragraph_1", "")
        
        # Extensive title validation and cleanup
        invalid_title_indicators = [
            "key references", "paragraph", 
            "approach", "we will use", 
            ", we will", "this idea performs",
            "**", "3**:", "2**:", "1**:"
        ]
        
        title_is_valid = title and not any(title.lower().startswith(indicator) or 
                                       indicator in title.lower() for indicator in invalid_title_indicators)
        
        # If the title is not valid, create a good one
        if not title_is_valid:
            # First try using the key idea
            if key_idea:
                # Remove anything after the first sentence
                first_sentence = re.split(r'[.!?]', key_idea)[0].strip()
                # Ensure it's not too long
                if len(first_sentence) < 50 and not any(indicator in first_sentence.lower() 
                                                     for indicator in invalid_title_indicators):
                    title = first_sentence
                else:
                    # Use first 47 chars of key idea if sentence is too long
                    title = key_idea[:47] + "..."
            # If no good key idea, try first paragraph
            elif paragraph_1:
                first_sentence = re.split(r'[.!?]', paragraph_1)[0].strip()
                if len(first_sentence) < 50:
                    title = first_sentence
                else:
                    title = paragraph_1[:47] + "..."
            else:
                # Last resort
                title = f"Research Idea #{rank}"
        
        # Final check for any remaining issues (titles starting with commas, etc.)
        if title.startswith(",") or title.startswith("to ") or title.startswith("es "):
            # Clean up by removing the prefix
            title = re.sub(r'^[,\s]+(to |es )?', '', title)
            
        # If still empty or invalid, use a generic title
        if not title or len(title) < 5:
            title = f"Research Idea #{rank}"
        
        # Truncate title if too long
        if len(title) > 50:
            title = title[:47] + "..."
            
        print(f"Rank {rank}: ELO {rating:.1f} - {title}")
    
    return final_sorted_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scientia v10: AI-driven scientific idea generation and evaluation")
    
    # Create a mutually exclusive group for research goal specification methods
    research_group = parser.add_mutually_exclusive_group(required=True)
    research_group.add_argument("--goal", nargs="+", dest="research_goal",
                          help="The research question or goal to explore (as command line arguments)")
    research_group.add_argument("--goal-file", dest="goal_file", type=str,
                          help="Path to a file containing the research question or goal")
    
    # Optional arguments
    parser.add_argument("-i", "--initial-ideas", type=int, default=20,
                        help="Number of initial ideas to generate (default: 20, no maximum limit)")
    parser.add_argument("-n", "--new-per-round", type=int, default=2,
                        help="Number of new ideas to generate per round (default: 2)")
    parser.add_argument("-f", "--final-ideas", type=int, default=5,
                        help="Number of ideas to include in final report (default: 5)")
    parser.add_argument("--rounds", type=int, default=4,
                        help="Number of evolution rounds to run (default: 4)")
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
                        help="Directory for storing output files and logs (will be used directly without creating subdirectories)")
    parser.add_argument("-c", "--config", type=str, default="model_servers.yaml",
                        help="Path to the model servers configuration file (default: model_servers.yaml)")
    
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
    main_client, MAIN_MODEL_ID, main_config = initialize_client(args.model, is_reflection=False, config_file=args.config)
    
    # Use reflection model if specified, otherwise use main model
    reflection_model = args.reflection_model if args.reflection_model else args.model
    reflection_client, REFLECTION_MODEL_ID, reflection_config = initialize_client(reflection_model, is_reflection=True, config_file=args.config)
    
    # For backward compatibility, also set the client and MODEL_ID variables
    client = main_client
    MODEL_ID = MAIN_MODEL_ID
    MODEL_CONFIG = main_config
    
    print(f"Generating {args.initial_ideas} ideas for research goal: {user_research_goal}")
    print(f"Running {args.rounds} evolution rounds")
    print(f"Allowing {args.new_per_round} new ideas per round")
    print(f"Will report top {args.final_ideas} ideas in final output")
    print(f"Idea bounds: min={min_ideas}, max={max_ideas} (adjustable via --min-ideas and --max-ideas)")
    print(f"Using main model: {args.model} ({MAIN_MODEL_ID})")
    if args.reflection_model:
        print(f"Using reflection model: {args.reflection_model} ({REFLECTION_MODEL_ID})")
    # Calculate replacement rate from new_per_round (for backward compatibility)
    replacement_rate = min(0.4, float(args.new_per_round) / args.initial_ideas)

    run_co_scientist_workflow(
        research_goal=user_research_goal,
        num_initial_ideas=args.initial_ideas,
        num_rounds=args.rounds,
        replacement_rate=replacement_rate,
        min_ideas=min_ideas,
        max_ideas=max_ideas,
        num_final_ideas=args.final_ideas,
        output_dir=args.output_dir
    )

# Example usage:
# 1. Specify research goal directly:
#    python scientia_v10.py --goal How can quantum computing improve machine learning?
#
# 2. Load research goal from a file:
#    python scientia_v10.py --goal-file research_questions.txt
#
# 3. Customize parameters:
#    python scientia_v10.py --goal-file research_questions.txt -i 20 --rounds 3 -f 10 --debug
#
# 4. Specify output directory:
#    python scientia_v10.py --goal-file FDXR.txt -o /path/to/output/directory
