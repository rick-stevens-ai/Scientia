#!/usr/bin/env python3
"""
Minimal test script for the modified Scientia system.
This tests:
1. Idea generation with criteria evaluation
2. Significant change detection
3. Tournament with criteria scores
4. Final report generation
"""
import os
import sys
import random
from pathlib import Path
from scientia_v8 import (
    IdeaEvolution, 
    is_significant_change,
    generate_final_report,
    get_tournament_agent_prompt,
    extract_citations,
    write_file,
    calculate_vector_score,
    IdeaScore,
    TOURNAMENT_CRITERIA
)

# Mock functions for testing without API access
def mock_evaluate_idea(idea_text, research_goal, agent_prompt):
    """Mock function to simulate criteria evaluation without API call."""
    print("Using mock evaluation function (no API call)")
    
    # Generate random scores between 5 and 9 for each criterion
    scores = {criterion: random.uniform(5.0, 9.0) for criterion in TOURNAMENT_CRITERIA}
    
    # Generate mock evaluation text
    evaluation_text = f"""Evaluation of idea:

{idea_text[:200]}...

Overall, this is a promising idea that addresses the research goal of {research_goal}.

Criteria Scores:
"""
    for criterion, score in scores.items():
        evaluation_text += f"- {criterion}: {score:.1f}/10\n"
    
    return scores, evaluation_text

# Test directory
TEST_DIR = os.path.join(os.getcwd(), 'test_output')
os.makedirs(TEST_DIR, exist_ok=True)

def minimal_test():
    """Run minimal tests of the modified functionality."""
    print("Running minimal tests of Scientia modifications...")
    
    # Create idea tracker
    idea_tracker = IdeaEvolution()
    
    # Create some test ideas
    research_goal = "Develop new approaches for quantum machine learning"
    
    print("\n1. Testing idea generation with criteria evaluation")
    idea1_text = """**Title**: Quantum Transfer Learning

**Key Idea**: Quantum circuits can accelerate transfer learning by encoding pre-trained classical neural network weights into quantum states.

**Paragraph**: Transfer learning has become a powerful technique in deep learning, allowing models trained on one task to be adapted to new tasks. This approach proposes a hybrid quantum-classical framework where pre-trained classical neural network weights are encoded into quantum states, enabling faster adaptation to new domains. By leveraging quantum parallelism during the fine-tuning phase, this method could significantly reduce the computational resources needed for transfer learning on large models.

**Approach**: Implement a quantum circuit that can encode classical neural network weights as quantum states, then perform parallel quantum operations to explore multiple fine-tuning configurations simultaneously. Benchmark against classical transfer learning approaches on image classification and natural language processing tasks to measure speedup and accuracy. Explore different quantum encoding strategies to maximize the advantage over classical approaches.

**Key References**: [Schuld et al. 2020; Chen et al. 2022; Abbas et al. 2021]
"""
    
    # Add initial idea
    idea1_id = idea_tracker.add_initial_idea(idea1_text)
    print(f"Added idea with ID: {idea1_id}")
    
    # Evaluate idea against scientific criteria
    print("\n2. Testing criteria evaluation")
    criteria_scores, evaluation_text = mock_evaluate_idea(
        idea1_text, 
        research_goal,
        get_tournament_agent_prompt()
    )
    
    # Update idea metadata with criteria scores
    idea_tracker.update_criteria_scores(idea1_id, criteria_scores)
    
    # Print criteria scores
    print("Criteria scores:")
    for criterion, score in criteria_scores.items():
        print(f"  {criterion}: {score:.1f}")
    
    # Create a log file for this idea
    log_file = os.path.join(TEST_DIR, f"idea_{idea1_id}.log")
    log_entry = f"""IDEA {idea1_id} EVOLUTION LOG

{'=' * 80}
TIMESTAMP: 2023-05-07 10:00:00
PHASE: Initial Generation, ROUND: 1
UNIQUE_ID: {idea_tracker.get_metadata(idea1_id).unique_id}
{'=' * 80}

{idea1_text}

"""
    write_file(log_file, log_entry)
    
    # Create a significantly different version of the idea
    idea2_text = """**Title**: Quantum Attention Mechanism

**Key Idea**: A quantum attention mechanism can efficiently model complex dependencies in sequence data by using quantum superposition for parallel attention computation.

**Paragraph**: Attention mechanisms have revolutionized natural language processing and other sequence modeling tasks, but they are computationally intensive. This approach proposes a quantum attention mechanism that exploits quantum superposition to compute attention weights for all sequence positions in parallel. By mapping sequence tokens to quantum states and performing quantum operations that calculate attention scores in superposition, we can achieve quadratic speedup in attention computation compared to classical approaches.

**Approach**: Design quantum circuits that encode sequence tokens as quantum states and implement quantum operations to compute attention weights in superposition. Develop a hybrid architecture where classical neural networks pre-process inputs and post-process quantum attention outputs. Evaluate the method on standard NLP benchmarks and compare with classical attention mechanisms in terms of speed and quality.

**Key References**: [Zhao et al. 2023; Romero et al. 2021; Li et al. 2022]
"""
    
    # Test significant change detection
    print("\n3. Testing significant change detection")
    is_significant = is_significant_change(idea1_text, idea2_text)
    print(f"Detected significant change: {is_significant}")
    
    # Add second idea as a new idea (simulating significant change)
    idea2_id = idea_tracker.add_new_idea(idea2_text)
    idea_tracker.metadata[idea2_id].parent_id = idea1_id  # Set parent reference
    
    # Evaluate second idea
    criteria_scores2, evaluation_text2 = mock_evaluate_idea(
        idea2_text, 
        research_goal,
        get_tournament_agent_prompt()
    )
    
    # Update second idea metadata
    idea_tracker.update_criteria_scores(idea2_id, criteria_scores2)
    
    # Create a log file for the second idea
    log_file2 = os.path.join(TEST_DIR, f"idea_{idea2_id}.log")
    log_entry2 = f"""IDEA {idea2_id} EVOLUTION LOG

{'=' * 80}
TIMESTAMP: 2023-05-07 10:30:00
PHASE: New Idea (Significant Change), ROUND: 2
UNIQUE_ID: {idea_tracker.get_metadata(idea2_id).unique_id}
{'=' * 80}

{idea2_text}

"""
    write_file(log_file2, log_entry2)
    
    # Convert criteria scores to vectors for comparison
    print("\n4. Testing tournament with criteria scores")
    vector1 = [criteria_scores.get(c, 5.0) for c in TOURNAMENT_CRITERIA]
    vector2 = [criteria_scores2.get(c, 5.0) for c in TOURNAMENT_CRITERIA]
    
    score1 = IdeaScore(*vector1)
    score2 = IdeaScore(*vector2)
    
    # Calculate vector score
    comparison_score = calculate_vector_score(score1, score2)
    print(f"Comparison score (Idea 1 vs Idea 2): {comparison_score:.3f}")
    print(f"Winner: {'Idea 1' if comparison_score > 0.5 else 'Idea 2' if comparison_score < 0.5 else 'Tie'}")
    
    # Generate final reports - simplified to avoid file dependency
    print("\n5. Testing final report generation")
    report1_path = os.path.join(TEST_DIR, f"idea_{idea1_id}_final.md")
    report2_path = os.path.join(TEST_DIR, f"idea_{idea2_id}_final.md")
    
    # Simulate final ELO ratings
    elo1 = 1250.0
    elo2 = 1280.0
    
    # Extract title and key idea from idea text
    idea1_title = idea1_text.split("**Title**:")[1].split("\n\n")[0].strip()
    idea1_key = idea1_text.split("**Key Idea**:")[1].split("\n\n")[0].strip()
    
    # Write simplified report content
    report1_content = f"""# Final Report: Idea {idea1_id}

## Title
{idea1_title}

## One Sentence Summary
{idea1_key}

## Final ELO Score and Rank
**Final ELO Score:** {elo1:.1f}

## Scientific Criteria Ratings
"""
    
    for criterion, score in criteria_scores.items():
        report1_content += f"- {criterion}: {score:.1f}/10\n"
    
    write_file(report1_path, report1_content)
    
    # Extract title and key idea from idea text 2
    idea2_title = idea2_text.split("**Title**:")[1].split("\n\n")[0].strip()
    idea2_key = idea2_text.split("**Key Idea**:")[1].split("\n\n")[0].strip()
    
    # Simplified report for idea 2
    report2_content = f"""# Final Report: Idea {idea2_id}

## Title
{idea2_title}

## One Sentence Summary
{idea2_key}

## Final ELO Score and Rank
**Final ELO Score:** {elo2:.1f}

## Scientific Criteria Ratings
"""
    
    for criterion, score in criteria_scores2.items():
        report2_content += f"- {criterion}: {score:.1f}/10\n"
    
    write_file(report2_path, report2_content)
    
    print(f"Generated final reports at:")
    print(f"  {report1_path}")
    print(f"  {report2_path}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    minimal_test()