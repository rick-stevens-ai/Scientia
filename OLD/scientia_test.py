#!/usr/bin/env python3
import os
import sys
import re
import json
import datetime
import time
import traceback
from pathlib import Path
from typing import List, Dict, Optional
from openai import OpenAI

# Initialize OpenAI client with API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set")
    sys.exit(1)

client = OpenAI(api_key=api_key)

# Configuration
MODEL_ID = "gpt-4"
DEBUG_MODE = True

def log_debug(message: str) -> None:
    """Log debug messages if debug mode is enabled."""
    if DEBUG_MODE:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DEBUG {timestamp}] {message}")

def generate_problem_name(research_goal: str, max_length: int = 30) -> str:
    """Generate a short, descriptive name for the research problem."""
    log_debug(f"Generating problem name from: {research_goal}")
    cleaned_goal = re.sub(r'[^a-zA-Z0-9\s]', '', research_goal).strip()
    words = cleaned_goal.split()
    if not words:
        return "research_problem"
    name = "_".join(words[:5]).lower()[:max_length].rstrip('_')
    result = name if name else "research_problem"
    log_debug(f"Generated problem name: {result}")
    return result

def create_scientia_directory(problem_name: str) -> Optional[str]:
    """Create a .scientia directory for the problem with versioning."""
    current_dir = os.getcwd()
    base_dir_name = f"{problem_name}.scientia"
    base_dir = os.path.join(current_dir, base_dir_name)
    
    def create_and_verify_dir(dir_path: str) -> bool:
        try:
            os.makedirs(dir_path, exist_ok=True)
            marker_file = os.path.join(dir_path, ".marker")
            with open(marker_file, 'w') as f:
                f.write(f"Created: {datetime.datetime.now().isoformat()}")
            return os.path.isdir(dir_path) and os.path.exists(marker_file)
        except Exception as e:
            print(f"Error creating directory {dir_path}: {e}")
            return False
    
    if not os.path.exists(base_dir):
        if create_and_verify_dir(base_dir):
            print(f"Created directory: {base_dir}")
            return base_dir
        return None
    
    version = 1
    while os.path.exists(os.path.join(current_dir, f"{base_dir_name}.{version}")):
        version += 1
    
    versioned_dir = os.path.join(current_dir, f"{base_dir_name}.{version}")
    if create_and_verify_dir(versioned_dir):
        print(f"Created versioned directory: {versioned_dir}")
        return versioned_dir
    return None

def write_file(file_path: str, content: str) -> bool:
    """Write content to a file with verification."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return os.path.exists(file_path)
    except Exception as e:
        print(f"Error writing file {file_path}: {e}")
        return False

def append_file(file_path: str, content: str) -> bool:
    """Append content to a file with verification."""
    try:
        file_size_before = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        return os.path.exists(file_path) and os.path.getsize(file_path) > file_size_before
    except Exception as e:
        print(f"Error appending to file {file_path}: {e}")
        return False

def log_idea(scientia_dir: str, idea_num: int, idea_text: str, phase: str, 
            round_num: Optional[int] = None, score: Optional[float] = None) -> bool:
    """Log an idea's current state to its log file."""
    log_file = os.path.join(scientia_dir, f"idea_{idea_num}.log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header = f"{'=' * 80}\nTIMESTAMP: {timestamp}\nPHASE: {phase}"
    if round_num is not None:
        header += f", ROUND: {round_num}"
    if score is not None:
        header += f", SCORE: {score:.1f}"
    header += f"\n{'=' * 80}\n\n"
    
    entry = header + idea_text + "\n\n"
    
    # Save checkpoint
    json_file = os.path.join(scientia_dir, f"idea_{idea_num}_{phase.lower().replace(' ', '_')}.json")
    json_content = json.dumps({
        "timestamp": timestamp,
        "phase": phase,
        "round": round_num,
        "score": score,
        "content": idea_text
    }, indent=2)
    
    if not write_file(json_file, json_content):
        return False
    
    if os.path.exists(log_file):
        return append_file(log_file, entry)
    else:
        return write_file(log_file, f"IDEA {idea_num} EVOLUTION LOG\n\n" + entry)

def log_progress(scientia_dir: str, phase: str, content: str) -> bool:
    """Log progress to a central progress file."""
    progress_file = os.path.join(scientia_dir, "progress.log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = f"\n{'=' * 40} {phase.upper()} - {timestamp} {'=' * 40}\n\n"
    entry += content + f"\n\n{'-' * 80}\n"
    
    # Save checkpoint
    checkpoint_file = os.path.join(scientia_dir, f"checkpoint_{phase.lower().replace(' ', '_')}.json")
    json_content = json.dumps({
        "timestamp": timestamp,
        "phase": phase,
        "content": content
    }, indent=2)
    
    if not write_file(checkpoint_file, json_content):
        return False
    
    if os.path.exists(progress_file):
        return append_file(progress_file, entry)
    else:
        return write_file(progress_file, "PROGRESS LOG\n\n" + entry)

def generate_final_report(scientia_dir: str, idea_num: int, idea_text: str, score: float) -> bool:
    """Generate a comprehensive final report for an idea."""
    report_file = os.path.join(scientia_dir, f"idea_{idea_num}_final.md")
    
    # Extract citations
    citation_pattern = r'\[(.*?\s+\d{4}(?:;\s*.*?\s+\d{4})*)\]'
    citations = re.findall(citation_pattern, idea_text)
    unique_citations = set()
    for citation_group in citations:
        for single_citation in re.split(r';\s*', citation_group):
            unique_citations.add(single_citation.strip())
    citations_list = sorted(list(unique_citations))
    
    report_content = f"""# Final Report: Idea {idea_num}

## Final Score: {score:.1f}

## Final Hypothesis

{idea_text}

## Evolution History

The evolution history is available in the idea_{idea_num}.log file.

"""
    
    if citations_list:
        report_content += "## Citations\n\n"
        for citation in citations_list:
            report_content += f"- {citation}\n"
    
    return write_file(report_file, report_content)

def run_test_workflow(research_goal: str, num_ideas: int = 2, num_rounds: int = 2) -> None:
    """Run a simplified workflow to test directory handling and file persistence."""
    print(f"Starting test workflow for: {research_goal}")
    
    try:
        # Create directory
        problem_name = generate_problem_name(research_goal)
        scientia_dir = create_scientia_directory(problem_name)
        
        if not scientia_dir:
            print("Error: Failed to create directory, exiting.")
            return
            
        # Log start
        log_progress(scientia_dir, "setup", 
                    f"Research goal: {research_goal}\n"
                    f"Number of ideas: {num_ideas}\n"
                    f"Number of rounds: {num_rounds}")
        
        # Generate initial ideas
        print("\nGenerating initial ideas...")
        initial_ideas = []
        
        for i in range(num_ideas):
            idea_text = (f"Hypothesis {i+1}: A novel approach to {research_goal} "
                        f"involving quantum effects and machine learning [Author 2024]. "
                        f"This approach could significantly improve our understanding by "
                        f"integrating multiple data sources [Smith 2023].")
            
            if log_idea(scientia_dir, i+1, idea_text, "Initial Generation", round_num=1):
                initial_ideas.append(idea_text)
                print(f"  Idea {i+1} generated and logged")
            else:
                print(f"  Error: Failed to log idea {i+1}")
                
        if not initial_ideas:
            print("Error: No ideas were successfully generated and logged")
            return
            
        log_progress(scientia_dir, "initial_generation", 
                    f"Generated {len(initial_ideas)} initial ideas")
        
        # Simulate evolution rounds
        ideas = initial_ideas.copy()
        
        for round_idx in range(2, num_rounds + 1):
            print(f"\nSimulating round {round_idx}...")
            evolved_ideas = []
            
            for i, idea in enumerate(ideas):
                improved_idea = (f"Refined hypothesis {i+1} for round {round_idx}: "
                               f"An enhanced approach to {research_goal} with "
                               f"quantitative improvements [Author 2024; Johnson 2023]. "
                               f"This method demonstrates 95% accuracy and builds on "
                               f"previous work while addressing key limitations "
                               f"[Smith 2023; Wilson 2024].")
                
                if log_idea(scientia_dir, i+1, improved_idea, "Evolution", round_idx):
                    evolved_ideas.append(improved_idea)
                    print(f"  Idea {i+1} evolved and logged for round {round_idx}")
                else:
                    print(f"  Error: Failed to log evolved idea {i+1} for round {round_idx}")
            
            ideas = evolved_ideas
            log_progress(scientia_dir, f"round_{round_idx}", 
                        f"Completed round {round_idx}, evolved {len(evolved_ideas)} ideas")
        
        # Generate final reports
        print("\nGenerating final scores and reports...")
        scores = [8.5, 7.8]  # Simulated scores
        
        # Create summary
        summary_content = f"# Research Summary: {problem_name}\n\n"
        summary_content += f"## Research Goal\n\n{research_goal}\n\n"
        summary_content += "## Ideas Ranked by Score\n\n"
        
        for i, (idea, score) in enumerate(zip(ideas, scores)):
            if generate_final_report(scientia_dir, i+1, idea, score):
                print(f"  Final report generated for idea {i+1}")
                summary_content += f"{i+1}. **[Idea {i+1}](idea_{i+1}_final.md)** - Score: {score:.1f}\n\n"
                summary_content += f"   {idea[:100]}...\n\n"
            else:
                print(f"  Error: Failed to generate final report for idea {i+1}")
        
        if write_file(os.path.join(scientia_dir, "summary.md"), summary_content):
            print(f"Summary file created: {os.path.join(scientia_dir, 'summary.md')}")
        else:
            print("Error: Failed to create summary file")
            
        log_progress(scientia_dir, "completion", 
                    f"Workflow completed successfully. Generated {len(ideas)} ideas "
                    f"across {num_rounds} rounds.")
        
        print(f"\nTest workflow completed successfully! Results saved in: {scientia_dir}")
        print(f"To verify persistence, check the directory and its contents.")
        
    except Exception as e:
        print(f"Error in workflow: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scientia_test.py <research_goal> [num_ideas] [num_rounds]")
        sys.exit(1)
        
    research_goal = sys.argv[1]
    num_ideas = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    num_rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    
    run_test_workflow(research_goal, num_ideas, num_rounds)
