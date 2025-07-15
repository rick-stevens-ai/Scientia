"""
Models for representing and tracking ideas in the Scientia system.

This module contains the core data structures for representing ideas,
tracking their evolution, and managing metadata.
"""

import datetime
import hashlib
import uuid
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional, Union, Set, NamedTuple

# Define tournament criteria list for consistent use throughout the code
# Emphasizing scientific and technical properties rather than social factors
TOURNAMENT_CRITERIA = [
    "Plausibility",              # Scientific plausibility
    "Theoretical Elegance",      # Simplicity, parsimony, and mathematical beauty
    "Mathematical Rigor",        # Formal mathematical foundation
    "First Principles",          # Derivation from fundamental principles
    "Symmetry Properties",       # Mathematical/physical symmetries and invariants
    "Information Theory",        # Information-theoretic aspects and entropy
    "Predictive Power",          # Ability to make testable predictions
    "Cross-domain Impact",       # Applicability across multiple domains
    "Novelty",                   # Uniqueness of the theoretical approach
    "Conceptual Foundations",    # Strength of underlying theoretical basis
    "Systems Properties",        # Emergent behaviors and complexity
    "Energy Efficiency",         # Theoretical energy requirements
    "Conservation Laws",         # Physical conservation principles
    "Dimensional Analysis",      # Mathematical/physical scaling relations
    "Quantum Properties",        # Quantum mechanical considerations
    "Computational Complexity",  # Algorithmic and computational aspects
    "Statistical Mechanics",     # Statistical and ensemble properties
    "Geometric Structure",       # Spatial/temporal geometric properties
    "Phase Transitions",         # Critical phenomena and transitions
    "Dynamical Stability"        # Stability and equilibrium properties
]


# IdeaScore class definition for tournament scoring
class IdeaScore(NamedTuple):
    """
    Immutable container for storing scores across tournament criteria.
    
    This is a named tuple with each field corresponding to one of the
    criteria in TOURNAMENT_CRITERIA.
    """
    # Core scientific properties
    plausibility: float              # Scientific plausibility rating
    theoretical_elegance: float      # Simplicity, parsimony, and beauty
    mathematical_rigor: float        # Formal mathematical foundation
    first_principles: float          # Fundamental principles basis
    symmetry_properties: float       # Mathematical/physical symmetries
    information_theory: float        # Information-theoretic aspects
    predictive_power: float          # Prediction capabilities
    cross_domain_impact: float       # Applicability across multiple domains
    
    # Theoretical and technical properties
    novelty: float                   # Uniqueness of theoretical approach
    conceptual_foundations: float    # Strength of underlying theory
    systems_properties: float        # Emergent behaviors and complexity
    energy_efficiency: float         # Energy requirements and optimization
    conservation_laws: float         # Physical conservation principles
    dimensional_analysis: float      # Mathematical/physical scaling relations
    
    # Advanced mathematical properties
    quantum_properties: float        # Quantum mechanical considerations
    computational_complexity: float  # Algorithmic and computational aspects
    statistical_mechanics: float     # Statistical and ensemble properties
    geometric_structure: float       # Spatial/temporal geometry
    phase_transitions: float         # Critical phenomena and transitions
    dynamical_stability: float       # Stability and equilibrium properties


@dataclass
class IdeaMetadata:
    """
    Tracks metadata for a single idea through its evolution.
    
    This class stores information about an idea including its identifiers,
    lineage, creation time, and scores.
    """
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
        """Initialize default values for mutable fields if not provided."""
        if self.elo_history is None:
            self.elo_history = [1200.0]  # Initial ELO rating
        if self.criteria_scores is None:
            self.criteria_scores = {}  # Empty dict for scores


class IdeaEvolution:
    """
    Manages the evolution and tracking of ideas through refinement cycles.
    
    This class maintains the mappings between idea IDs and their content,
    manages metadata, and provides methods for adding, refining, and tracking
    ideas through their evolutionary process.
    """
    def __init__(self):
        """Initialize the idea tracking structures."""
        self.ideas: Dict[int, str] = {}  # Current idea texts by numeric ID
        self.metadata: Dict[int, IdeaMetadata] = {}  # Idea metadata by numeric ID
        self.unique_id_map: Dict[str, int] = {}  # Maps unique IDs to numeric IDs
        self.next_id: int = 1
        self.refined_pairs: Set[Tuple[int, int]] = set()  # Track refinement relationships
        
    def add_initial_idea(self, idea_text: str) -> int:
        """
        Add an initial idea and return its ID.
        
        Args:
            idea_text: The text content of the new idea
            
        Returns:
            The numeric ID assigned to the new idea
        """
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
        """
        Add a refined version of an existing idea.
        
        Args:
            original_id: The ID of the original idea being refined
            refined_text: The text content of the refined idea
            
        Returns:
            The numeric ID assigned to the new refined idea
            
        Raises:
            ValueError: If the original idea ID is not found
        """
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
        """
        Add a completely new idea generated during evolution.
        
        Args:
            idea_text: The text content of the new idea
            
        Returns:
            The numeric ID assigned to the new idea
        """
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
        """
        Get the evolution history of an idea.
        
        Args:
            idea_id: The ID of the idea to get history for
            
        Returns:
            A list of idea texts in chronological order, starting with the
            earliest ancestor and ending with the current idea
            
        Raises:
            ValueError: If the idea ID is not found
        """
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
        """
        Update the ELO history for an idea.
        
        Args:
            idea_id: The ID of the idea to update
            new_elo: The new ELO rating to add to history
            
        Raises:
            ValueError: If the idea ID is not found
        """
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        self.metadata[idea_id].elo_history.append(new_elo)
        
    def record_tournament_match(self, idea_id: int):
        """
        Record that an idea participated in a tournament match.
        
        Args:
            idea_id: The ID of the idea that participated
            
        Raises:
            ValueError: If the idea ID is not found
        """
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        self.metadata[idea_id].tournament_matches += 1
        
    def update_criteria_scores(self, idea_id: int, scores: Dict[str, float]):
        """
        Update the scientific criteria scores for an idea.
        
        Args:
            idea_id: The ID of the idea to update
            scores: Dictionary mapping criteria names to scores
            
        Raises:
            ValueError: If the idea ID is not found
        """
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        self.metadata[idea_id].criteria_scores.update(scores)
        
    def get_all_ideas(self) -> Dict[int, str]:
        """
        Get all current ideas.
        
        Returns:
            Dictionary mapping idea IDs to their text content
        """
        return self.ideas.copy()
        
    def get_metadata(self, idea_id: int) -> IdeaMetadata:
        """
        Get metadata for a specific idea.
        
        Args:
            idea_id: The ID of the idea to get metadata for
            
        Returns:
            The metadata object for the specified idea
            
        Raises:
            ValueError: If the idea ID is not found
        """
        if idea_id not in self.metadata:
            raise ValueError(f"Idea {idea_id} not found")
        return self.metadata[idea_id]
        
    def get_id_by_unique_id(self, unique_id: str) -> Optional[int]:
        """
        Get the numeric ID for a given unique ID.
        
        Args:
            unique_id: The unique identifier to look up
            
        Returns:
            The corresponding numeric ID, or None if not found
        """
        return self.unique_id_map.get(unique_id)
        
    def get_unique_id(self, idea_id: int) -> Optional[str]:
        """
        Get the unique ID for a given numeric ID.
        
        Args:
            idea_id: The numeric ID to look up
            
        Returns:
            The corresponding unique ID, or None if not found
        """
        if idea_id not in self.metadata:
            return None
        return self.metadata[idea_id].unique_id


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
