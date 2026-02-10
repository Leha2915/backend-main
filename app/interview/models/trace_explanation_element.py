from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..interview_tree.node import Node


class TraceExplanationElement:
    """
    Connects a tree node with a chat interaction.
    Provides traceability between knowledge elements and the conversation.
    """

    def __init__(self, interaction_id: str, node_ref: Any):
        """
        Initializes a trace element.

        Args:
            node_ref: Reference to the associated node
            interaction_id: ID of the associated chat interaction
        """
        self.node = node_ref
        self.interaction_id = interaction_id

    def to_dict(self) -> Dict[str, Any]:
        """Converts the trace element to a dictionary for JSON serialization."""
        return {
            "node_id": self.node.id if self.node else None,
            "interaction_id": self.interaction_id
        }

    def get_node(self) -> 'Node':
        """Returns the associated node."""
        return self.node

    def get_interaction_id(self) -> str:
        """Returns the ID of the associated chat interaction."""
        return self.interaction_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceExplanationElement":
        """
        Creates a trace element from a dictionary.
        The node reference (node) must be set separately (e.g., via mapping during tree reconstruction).
        
        Args:
            data: Dictionary containing trace element data
            
        Returns:
            A new TraceExplanationElement instance
        """
        return cls(
            interaction_id=data.get("interaction_id", ""),
            node_ref=None  # Will be set later during tree reconstruction
        )