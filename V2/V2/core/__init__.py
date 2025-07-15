"""
Core modules for the Scientia system.

This package contains the core functionality for generating, evaluating,
and evolving scientific ideas.
"""

from .models import (
    TOURNAMENT_CRITERIA,
    IdeaScore,
    IdeaMetadata,
    IdeaEvolution,
    generate_unique_idea_id
)

from .agents import (
    call_agent,
    initialize_client,
    load_model_configs,
    get_generation_agent_prompt,
    get_ranking_agent_prompt,
    get_evolution_agent_prompt,
    get_proximity_check_agent_prompt,
    get_reflection_agent_prompt,
    get_tournament_agent_prompt,
    get_meta_review_agent_prompt,
    get_supervisor_agent_prompt,
    DEBUG_MODE
)

from .tournament import (
    calculate_vector_score,
    calculate_elo_update,
    compute_idea_score_vectors,
    run_optimized_tournament
)

from .file_utils import (
    generate_problem_name,
    create_scientia_directory,
    log_idea,
    save_checkpoint,
    load_checkpoint,
    write_file,
    append_file,
    create_directory,
    log_debug
)

from .idea_parser import (
    parse_structured_idea,
    format_structured_idea,
    parse_ideas_from_text,
    parse_ideas_order_from_ranking,
    extract_citations,
    is_significant_change
)

from .evaluation import (
    evaluate_idea_with_criteria,
    extract_idea_specific_feedback,
    generate_final_report
)

__all__ = [
    # Models
    'TOURNAMENT_CRITERIA',
    'IdeaScore',
    'IdeaMetadata',
    'IdeaEvolution',
    'generate_unique_idea_id',
    
    # Agents
    'call_agent',
    'initialize_client',
    'load_model_configs',
    'get_generation_agent_prompt',
    'get_ranking_agent_prompt',
    'get_evolution_agent_prompt',
    'get_proximity_check_agent_prompt',
    'get_reflection_agent_prompt',
    'get_tournament_agent_prompt',
    'get_meta_review_agent_prompt',
    'get_supervisor_agent_prompt',
    'DEBUG_MODE',
    
    # Tournament
    'calculate_vector_score',
    'calculate_elo_update',
    'compute_idea_score_vectors',
    'run_optimized_tournament',
    
    # File Utils
    'generate_problem_name',
    'create_scientia_directory',
    'log_idea',
    'save_checkpoint',
    'load_checkpoint',
    'write_file',
    'append_file',
    'create_directory',
    'log_debug',
    
    # Idea Parser
    'parse_structured_idea',
    'format_structured_idea',
    'parse_ideas_from_text',
    'parse_ideas_order_from_ranking',
    'extract_citations',
    'is_significant_change',
    
    # Evaluation
    'evaluate_idea_with_criteria',
    'extract_idea_specific_feedback',
    'generate_final_report'
]
