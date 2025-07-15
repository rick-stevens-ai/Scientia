"""
Agents module for interfacing with AI models in the Scientia system.

This module contains functions for generating agent-specific prompts
and making API calls to the language models.
"""

import os
import sys
import time
import traceback
import yaml
from typing import List, Dict, Any, Optional

from openai import OpenAI
from openai import APIError, APITimeoutError, APIConnectionError, RateLimitError

# Initialize configuration variables
MODEL_TIMEOUT = 120.0  # Timeout in seconds (increased to handle larger responses)
MAX_RETRIES_TIMEOUT = 3  # Maximum retries for timeout errors
DEBUG_MODE = False      # Disable detailed logging by default (can be enabled via --debug flag)

# Client instances for different models
main_client = None
reflection_client = None
MAIN_MODEL_ID = None
REFLECTION_MODEL_ID = None

# These will be set after parsing command line arguments
MODEL_CONFIG = None
MODEL_ID = None
client = None


def log_debug(message: str) -> None:
    """
    Log debug messages if debug mode is enabled.
    
    Args:
        message: Debug message to log
    """
    if DEBUG_MODE:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DEBUG {timestamp}] {message}")


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


def initialize_client(model_shortname='gpt41', is_reflection=False):
    """
    Initialize the OpenAI client based on the selected model configuration.
    
    Args:
        model_shortname: Shortname of the model to use
        is_reflection: Whether this client is for the reflection agent
        
    Returns:
        Tuple of (client, model_id, config)
    """
    global MAIN_MODEL_ID, REFLECTION_MODEL_ID, MODEL_ID
    
    # Load model configurations
    models = load_model_configs()
    
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


def get_ranking_agent_prompt():
    """
    The Ranking Agent compares and ranks competing hypotheses or proposals,
    considering multiple criteria with emphasis on mathematical, physical,
    and theoretical properties.
    """
    return (
        "You receive multiple research ideas or proposals, each containing an explicit "
        "hypothesis. Compare and rank them based on twenty key criteria: \n\n"
        
        "Core scientific properties:\n"
        "(1) Plausibility - scientific and technical feasibility\n"
        "(2) Theoretical Elegance - simplicity, parsimony, and mathematical beauty\n"
        "(3) Mathematical Rigor - formal mathematical foundation\n"
        "(4) First Principles - derivation from fundamental scientific principles\n"
        "(5) Symmetry Properties - mathematical/physical symmetries and invariants\n"
        "(6) Information Theory - information-theoretic aspects and entropy\n"
        "(7) Predictive Power - ability to make specific, testable predictions\n"
        "(8) Cross-domain Impact - applicability across multiple domains\n\n"
        
        "Theoretical and technical properties:\n"
        "(9) Novelty - uniqueness of the theoretical approach\n"
        "(10) Conceptual Foundations - strength of underlying theoretical basis\n"
        "(11) Systems Properties - emergent behaviors and complexity\n"
        "(12) Energy Efficiency - theoretical energy requirements\n"
        "(13) Conservation Laws - physical conservation principles\n"
        "(14) Dimensional Analysis - mathematical/physical scaling relations\n\n"
        
        "Advanced mathematical properties:\n"
        "(15) Quantum Properties - quantum mechanical considerations\n"
        "(16) Computational Complexity - algorithmic and computational aspects\n"
        "(17) Statistical Mechanics - statistical and ensemble properties\n"
        "(18) Geometric Structure - spatial/temporal geometric properties\n"
        "(19) Phase Transitions - critical phenomena and transitions\n"
        "(20) Dynamical Stability - stability and equilibrium properties\n\n"
        
        "For each idea, evaluate all criteria and provide a final ranking with "
        "detailed rationale emphasizing theoretical and technical merits. Pay "
        "particular attention to mathematical properties, elegance, symmetry, and "
        "foundational principles."
    )


def get_evolution_agent_prompt():
    """
    The Evolution Agent has two main functions: (1) refine existing ideas by simplifying, 
    extending, or combining them with other concepts, and (2) generate entirely new ideas 
    to expand the solution space. Each idea must contain an explicit hypothesis statement
    with appropriate citations.
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
        
        "3. GENERATE ADDITIONAL NEW IDEAS (Secondary Task):\n"
        "   - After refining existing ideas and creating significant-change new ideas\n"
        "   - Generate additional NEW complementary ideas to meet your target\n"
        "   - These should explore novel angles not covered by existing ideas\n"
        "   - Ensure new ideas maintain the same structured format\n"
        "   - Include multiple relevant citations to support new hypotheses\n\n"
        
        "REQUIRED FORMAT FOR ALL IDEAS (Refined or New):\n"
        "1. **Title**: A concise, descriptive title\n"
        "2. **Key Idea**: Single sentence stating the core hypothesis\n"
        "3. **Paragraph**: Detailed explanation of importance and uniqueness\n"
        "4. **Approach**: Methods for implementation or testing\n"
        "5. **Key References**: Citations in [Author Year] format\n\n"
        
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
        "by citations in [Author Year] format."
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
    vector-based scoring across technical and theoretical criteria.
    """
    return (
        "You are the Tournament Agent in a multi-agent AI co-scientist system. "
        "For each pair of ideas, evaluate them across these twenty criteria "
        "and provide numerical scores in EXACTLY this format:\n\n"
        "Criterion 1 (Plausibility): Idea A = X, Idea B = Y\n"
        "Criterion 2 (Theoretical Elegance): Idea A = X, Idea B = Y\n"
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
        agent_name: Name of the agent (used for selecting client and display)
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

