"""
Node class representing a single node in the ACV interview tree.
This is a core data structure class that models hierarchical relationships.
"""

from typing import Optional, List, Dict, Any
from .node_label import NodeLabel
from ..models.trace_explanation_element import TraceExplanationElement
import logging
import uuid
import time

logger = logging.getLogger(__name__)


class Node:
    """
    Node class representing an element in the ACV interview tree.
    Each node has a label (type), conclusion text, and relationships to other nodes.
    Uses UUIDs for IDs and a monotonic timestamp to determine recency.
    """

    def __repr__(self):
        return f"<Node label={self.label} content={self.conclusion} parent={self.parents}>"

    def __init__(
        self,
        label: NodeLabel,
        conclusion: Optional[str] = None,
        parents: Optional[List['Node']] = None,
        trace: Optional[List['TraceExplanationElement']] = None,
        is_value_path_completed: Optional[bool] = False,
        id: Optional[str] = None,
        created_ns: Optional[int] = None
    ):
        """
        Initialize a new node in the ACV interview tree.

        Args:
            label: Node type (ATTRIBUTE, CONSEQUENCE, VALUE, etc.)
            conclusion: Text content/summary of the node
            parents: List of parent nodes
            trace: List of trace elements explaining node creation
            is_value_path_completed: Whether this node is part of a completed value path
            id: Optional explicit ID (string, UUID). If omitted, a UUIDv4 is generated.
            created_ns: Optional monotonic creation timestamp (nanoseconds). If omitted, time.monotonic_ns() is used.
        """
        self.label = label

        # ID assignment via UUID (string)
        if id is not None:
            self.id = str(id)
            self.is_value_path_completed = bool(is_value_path_completed)
        else:
            self.id = str(uuid.uuid4())
            self.is_value_path_completed = (label == NodeLabel.VALUE)

        # Monotonic creation time for "latest parent" logic
        self.created_ns = int(created_ns) if created_ns is not None else time.monotonic_ns()

        # Initialize other properties
        self.conclusion = conclusion
        self.parents: List['Node'] = parents if parents else []
        self.children: List['Node'] = []
        self.trace = trace if trace else []
        self.backwards_relations: List['Node'] = []

    def get_parents(self) -> List['Node']:
        """Get all parent nodes of this node."""
        return self.parents

    def get_children(self) -> List['Node']:
        """Get all child nodes of this node."""
        return self.children

    def get_label(self) -> NodeLabel:
        """Get the label (type) of this node."""
        return self.label

    def get_conclusion(self) -> Optional[str]:
        """Get the conclusion text of this node."""
        return self.conclusion

    def get_value_path_completed(self) -> bool:
        """Check if this node is part of a completed value path."""
        return self.is_value_path_completed

    def set_conclusion(self, conclusion: str):
        """
        Update the conclusion text of this node.
        Used for graph optimization when an existing node gets a new conclusion.

        Args:
            conclusion: New conclusion text
        """
        self.conclusion = conclusion

    def set_value_path_completed(self, completed: bool):
        """
        Set whether this node is part of a completed value path.

        Args:
            completed: Value path completion status
        """
        self.is_value_path_completed = completed

    def add_child(self, child: 'Node'):
        """
        Add a child node to this node and establish bidirectional relationship.

        Args:
            child: The child node to add
        """
        if child not in self.children:
            self.children.append(child)
        if self not in child.parents:
            child.parents.append(self)

    def add_parent(self, parent: 'Node'):
        """
        Add a parent node to this node and establish bidirectional relationship.

        Args:
            parent: The parent node to add
        """
        if parent not in self.parents:
            self.parents.append(parent)
        if self not in parent.children:
            parent.children.append(self)

    def remove_child(self, child_node: 'Node'):
        """
        Remove a child node from this node's children list.

        Args:
            child_node: The child node to remove
        """
        if child_node in self.children:
            self.children.remove(child_node)
            logger.debug(
                f"Removed node {child_node.id} from children of node {self.id}")

    def add_trace(self, trace_elem: TraceExplanationElement):
        """
        Add a trace element to this node, avoiding duplicates.
        Trace elements explain why and how this node was created.

        Args:
            trace_elem: Trace element to add
        """
        # Initialize trace list if not present
        if not hasattr(self, 'trace'):
            self.trace = []

        # Check for duplicates based on interaction_id
        if trace_elem and trace_elem.get_interaction_id():
            for existing_elem in self.trace:
                if existing_elem.get_interaction_id() == trace_elem.get_interaction_id():
                    # Duplicate found, don't add
                    return

        # Add if not a duplicate
        self.trace.append(trace_elem)

    def add_backwards_relation(self, related_node: 'Node'):
        """
        Add a node to the list of backwards relations.
        Used when a node is identified outside the usual hierarchical
        order (e.g., an attribute after a consequence).

        Args:
            related_node: The node found in reverse order
        """
        if related_node not in self.backwards_relations:
            self.backwards_relations.append(related_node)

    def get_backwards_relations(self) -> List['Node']:
        """
        Get the list of backwards relations.

        Returns:
            List of nodes found in reverse hierarchical order
        """
        return self.backwards_relations

    def get_latest_parent(self) -> Optional['Node']:
        """
        Get the parent node with the most recent creation timestamp.
        This replaces the old heuristic based on the highest numeric ID.
        """
        if not self.parents:
            return None
        return max(self.parents, key=lambda parent: getattr(parent, "created_ns", 0))

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this node to a dictionary for serialization.

        Returns:
            Dictionary representation of the node
        """
        return {
            "id": self.id,  # string (UUID)
            "label": self.label.value,
            "conclusion": self.get_conclusion(),
            "trace": [t.to_dict() for t in self.trace],
            "is_value_path_completed": self.is_value_path_completed,
            "parents": [p.id for p in self.parents],
            "children": [c.id for c in self.children],
            "backwards_relations": [n.id for n in self.backwards_relations],
            "created_ns": self.created_ns,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """
        Create a node from a dictionary representation.

        Args:
            data: Dictionary representation of the node

        Returns:
            The reconstructed node
        """
        trace = [TraceExplanationElement.from_dict(
            t) for t in data.get("trace", [])]
        n = cls(
            id=str(data["id"]),
            label=NodeLabel(data["label"]),
            conclusion=data.get("conclusion"),
            trace=trace,
            is_value_path_completed=data.get("is_value_path_completed", False),
            created_ns=data.get("created_ns")
        )
        # Parents and children are set later
        # Backwards-relations are set after loading all nodes
        n._pending_backwards_relations = data.get("backwards_relations", [])
        return n
