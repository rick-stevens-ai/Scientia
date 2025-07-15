"""
File and directory utilities for the Scientia system.

This module contains functions for file operations, directory management,
and file system interactions needed by the Scientia system.
"""

import os
import sys
import re
import pickle
import datetime
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

# Configuration variables for file operations
DEBUG_MODE = False      # Disable detailed logging by default (can be enabled via --debug flag)
CHECKPOINT_FREQ = True  # Enable state checkpointing
AUTO_BACKUP = True      # Enable automatic backups
MAX_BACKUPS = 3        # Maximum number of backup files to keep
RECOVERY_ENABLED = True # Enable automatic recovery from checkpoints


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


def log_idea(scientia_dir: str, idea_num: int, idea_text: str, phase: str, 
             round_num: Optional[int] = None, elo_score: Optional[float] = None,
             unique_id: Optional[str] = None, metadata: Optional[Any] = None) -> bool:
    """
    Log an idea's current state to its dedicated log file.
    
    Args:
        scientia_dir: Path to the .scientia directory
        idea_num: The idea's number/ID
        idea_text: The current text/content of the idea
        phase: Current phase (e.g., "Initial Generation", "Evolution", "Tournament")
        round_num: Current round number (if applicable)
        elo_score: Current ELO score (if applicable)
        unique_id: Unique identifier for the idea (if available)
        metadata: Metadata object for the idea (if available)
        
    Returns:
        True if logging was successful, False otherwise
    """
    try:
        # Create standard log file and unique ID-based file name if available
        log_file = os.path.join(scientia_dir, f"idea_{idea_num}.log")
        unique_log_file = os.path.join(scientia_dir, f"idea_{unique_id}.md") if unique_id else None
        
        # Prepare log entry with timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        
        # Log to unique ID file if available
        unique_log_success = True
        if unique_log_file:
            md_header = f"# Idea {idea_num}: Evolution Log\n\n"
            if metadata and hasattr(metadata, 'unique_id'):
                md_header += f"**Unique ID:** {metadata.unique_id}\n\n"
            
            md_entry = f"## {phase}"
            if round_num is not None:
                md_entry += f" (Round {round_num})"
            md_entry += f"\n\n**Timestamp:** {timestamp}\n\n"
            
            if elo_score is not None:
                md_entry += f"**ELO Score:** {elo_score:.1f}\n\n"
                
            if metadata and hasattr(metadata, 'criteria_scores') and metadata.criteria_scores:
                md_entry += "**Scientific Criteria Scores:**\n\n"
                for criterion, score in metadata.criteria_scores.items():
                    md_entry += f"- {criterion}: {score:.1f}\n"
                md_entry += "\n"
                
            md_entry += "**Content:**\n\n"
            md_entry += idea_text + "\n\n"
            md_entry += "---\n\n"
            
            if os.path.exists(unique_log_file):
                unique_log_success = append_file(unique_log_file, md_entry)
            else:
                unique_log_success = write_file(unique_log_file, md_header + md_entry)
                
        return standard_log_success and unique_log_success
            
    except Exception as e:
        print(f"Error logging idea {idea_num}: {e}")
        traceback.print_exc()
        return False


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
