"""
Node utilities module for common node operations.
Provides functions for managing and querying nodes in the interview tree.
"""

from typing import Tuple
from app.interview.interview_tree.node_label import NodeLabel

class NodeUtils:
    """
    Utility class for common node operations.
    """
    
    # Flag for automatically generated nodes
    AUTO_GENERATED_PREFIX = "AUTO: "
    
    @classmethod
    def create_auto_generated_node(cls, label: NodeLabel) -> Tuple[NodeLabel, str, bool]:
        """
        Creates a summary for an automatically generated node.
        
        Args:
            label: NodeLabel for the auto-generated node
            
        Returns:
            Tuple of (NodeLabel, summary, is_auto_generated=True)
        """
        descriptions = {
            NodeLabel.ATTRIBUTE: "Automatically generated product attribute",
            NodeLabel.CONSEQUENCE: "Automatically generated consequence",
            NodeLabel.VALUE: "Automatically generated value",
            NodeLabel.IDEA: "Automatically generated idea"
        }
        
        summary = cls.AUTO_GENERATED_PREFIX + descriptions.get(label, "Automatically generated node")
        return label, summary, True
    
    @classmethod
    def is_auto_generated(cls, summary: str) -> bool:
        """
        Checks if a summary belongs to an automatically generated node.
        
        Args:
            summary: Summary to check
            
        Returns:
            True if it's an automatically generated node
        """
        return summary and summary.startswith(cls.AUTO_GENERATED_PREFIX)