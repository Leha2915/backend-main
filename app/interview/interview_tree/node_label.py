"""
Node label definitions and hierarchy for the ACV interview model.
Defines the types of nodes and their hierarchical relationships.
"""

from enum import Enum
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class NodeLabel(Enum):
    """
    Enumeration of node types in the ACV interview model.
    Defines the possible types of nodes in the hierarchical tree.
    """
    TOPIC = "Topic"
    STIMULUS = "Stimulus"
    IDEA = "Idea"
    ATTRIBUTE = "A"
    CONSEQUENCE = "C"
    VALUE = "V"
    IRRELEVANT_ANSWER = "Irrelevant Answer"

# Node hierarchy constant excluding IRRELEVANT_ANSWER
NODE_HIERARCHY = [label for label in NodeLabel if label != NodeLabel.IRRELEVANT_ANSWER]

class NodeLabelUtils:
    """
    Utility functions for working with NodeLabel hierarchy.
    """
    
    @staticmethod
    def get_relative_label(label: NodeLabel, offset: int) -> Optional[NodeLabel]:
        """
        Get the label with the given offset in the hierarchy.
        
        Args:
            label: Starting node label
            offset: Relative position (-1: previous, +1: next)
            
        Returns:
            Label at the relative position or None if out of bounds
        """
        try:
            index = NODE_HIERARCHY.index(label)
            new_index = index + offset
            if 0 <= new_index < len(NODE_HIERARCHY):
                return NODE_HIERARCHY[new_index]
            logger.debug(f"Hierarchy {offset} for label {label} is out of bounds")
            return None
        except ValueError:
            logger.debug(f"Label {label} is not in the hierarchy")
            return None

    @staticmethod
    def get_previous(label: NodeLabel) -> Optional[NodeLabel]:
        """
        Get the previous label in the hierarchy.
        
        Args:
            label: Current label
            
        Returns:
            Previous label in hierarchy or None
        """
        return NodeLabelUtils.get_relative_label(label, -1)

    @staticmethod
    def get_next(label: NodeLabel) -> Optional[NodeLabel]:
        """
        Get the next label in the hierarchy.
        
        Args:
            label: Current label
            
        Returns:
            Next label in hierarchy or None
        """
        return NodeLabelUtils.get_relative_label(label, 1)






