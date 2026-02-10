"""
Queue Manager for the Interview Engine.
Manages a hierarchical queue with priority rules.
"""

import logging
from typing import List, Dict, Any, Optional

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Manages a hierarchical queue with specific priority order based on node hierarchy:
    Stimulus -> IDEA -> ATTRIBUTE -> CONSEQUENCE -> VALUE

    Priority rules:
    - Nodes with higher hierarchy position have higher priority
    - IDEAS are directly set as active (not in queue)
    - VALUES are never added to queue or set as active
    """

    # Constants
    MAX_UNCHANGED_COUNT = 3
    MAX_QUEUE_PREVIEW_ITEMS = 5
    MAX_CONTENT_PREVIEW_LENGTH = 30

    def __init__(self):
        self.tree = None
        self.init_new()

    def init_new(self):
        """Initialize a new empty queue."""
        # Single queue for all node types in priority order
        self.queue: List[Node] = []
        self.active_node: Optional[Node] = None
        self.active_node_unchanged_count = 0

    def set_tree(self, tree_instance):
        """Set the tree instance for this queue manager."""
        self.tree = tree_instance

    def initialize_stimuli_queue(self, stimulus_nodes: List[Node]) -> None:
        """
        Initialize the queue with stimulus nodes in the order they were received.

        Args:
            stimulus_nodes: List of stimulus nodes to add to the queue
        """
        self.queue.clear()
        self.queue.extend(stimulus_nodes)

        logger.info(f"Queue initialized with {len(self.queue)} stimuli")

        first_stimulus = self.queue.pop(0)
        self.tree.set_active_node(first_stimulus)
        self.active_node = first_stimulus

        logger.info(
            f"First stimulus set as active node: {first_stimulus.get_label().value}"
        )

    def _set_active_node(self, node_obj: Node) -> None:
        """
        Helper method to set the active node.

        Args:
            node_obj: The node to set as active
        """
        self.active_node = node_obj
        self.active_node_unchanged_count = 0
        if self.tree is not None:
            self.tree.set_active_node(node_obj)

    def add_to_queue(self, node_obj: Node) -> None:
        """
        Add a node to the queue based on its label and priority rules.
        - IDEAS are directly set as active (not in queue)
        - VALUES are never added to queue
        - All other types are sorted by hierarchy
        - Prevents duplicate entries of the same node in the queue by merging with unprocessed nodes

        Args:
            node_obj: Node to add to the queue
        """
        if not node_obj:
            return

        label = node_obj.get_label()

        if label == NodeLabel.IDEA:
            logger.info(
                f"IDEA '{node_obj.get_conclusion()}' directly set as active"
            )
            # Remove irrelevant answer nodes if present
            if self.active_node and self.active_node.get_label() == NodeLabel.IRRELEVANT_ANSWER:
                self.tree.remove_irrelevant_node()
            self._set_active_node(node_obj)
            return

        elif label == NodeLabel.VALUE:
            logger.info(
                f"VALUE '{node_obj.get_conclusion()}' detected (not added to queue)"
            )
            # Remove irrelevant answer nodes if present
            if self.active_node and self.active_node.get_label() == NodeLabel.IRRELEVANT_ANSWER:
                self.tree.remove_irrelevant_node()
                # Synchronize active_node with tree.active
                self.active_node = self.tree.active
            return

        elif label == NodeLabel.IRRELEVANT_ANSWER:
            logger.info(
                f"IRRELEVANT_ANSWER '{node_obj.get_conclusion()}' detected - will be stacked"
            )

            # If this is stacking onto an existing irrelevant node (same ID),
            # don't reset the counter
            if self.active_node and self.active_node.get_label() == NodeLabel.IRRELEVANT_ANSWER:
                # Just update the active node without resetting the counter
                self.active_node = node_obj
                if self.tree is not None:
                    self.tree.set_active_node(node_obj)
            else:
                # This is a new irrelevant node, not stacking
                self._set_active_node(node_obj)
            return

        # Check if the node is already in the queue - due to merging unprocessed nodes
        for existing_node in self.queue:
            if existing_node.id == node_obj.id:
                logger.warning(
                    f"{label.value} with ID {node_obj.id} already in queue - not added again"
                )
                return

        # Determine insertion position and insert node
        insert_pos = self._get_insert_position(label)

        self.queue.insert(insert_pos, node_obj)
        logger.info(
            f"{label.value} inserted at position {insert_pos} (Queue: {len(self.queue)} nodes)"
        )

    def _get_insert_position(self, label: NodeLabel) -> int:
        """
        Determine insertion position for Attribute and Consequence nodes.

        Rules for Consequences:
        - Always insert at the front (since many detected Consequences were already inverted)

        Rules for Attributes:
        - Always insert after the last Attribute in the queue
        - If no Attribute in the queue, insert after the last Consequence

        Args:
            label: Label of the node to insert

        Returns:
            Position in the queue where the node should be inserted
        """
        # Only for Attributes and Consequences
        if label != NodeLabel.ATTRIBUTE and label != NodeLabel.CONSEQUENCE:
            return len(self.queue)

        # Empty queue? Insert at beginning
        if not self.queue:
            return 0

        # Find the position of the last node of each type
        last_c_pos = -1
        last_a_pos = -1

        for i, node in enumerate(self.queue):
            if node.get_label() == NodeLabel.CONSEQUENCE:
                last_c_pos = i
            elif node.get_label() == NodeLabel.ATTRIBUTE:
                last_a_pos = i

        # Decide based on label where to insert
        if label == NodeLabel.CONSEQUENCE:
            # Always insert new consequences at the beginning of the queue
            # This ensures they are processed before attributes
            return 0
        else:  # label == NodeLabel.ATTRIBUTE
            # Insert after the last Attribute
            if last_a_pos >= 0:
                return last_a_pos + 1
            # If no Attributes, insert after the last Consequence
            elif last_c_pos >= 0:
                return last_c_pos + 1
            # If neither Attributes nor Consequences, insert at end
            else:
                return len(self.queue)

    def update_unchanged_count(self, has_required_element: bool) -> None:
        """
        Update the counter for how many times the active node has remained unchanged.

        Args:
            has_required_element: Whether a required element was found
        """
        if has_required_element:
            self.active_node_unchanged_count = 0
        else:
            self.active_node_unchanged_count += 1
            logger.warning(
                f"Active node unchanged: {self.active_node_unchanged_count}/{self.MAX_UNCHANGED_COUNT}"
            )

    def should_move_to_next_node(self) -> bool:
        """
        Check if we should move to the next node in the queue.

        Returns:
            True if we should move to the next node, False otherwise
        """
        return self.active_node_unchanged_count >= self.MAX_UNCHANGED_COUNT

    def get_next_active_node(self) -> Optional[Node]:
        """
        Remove the next node from the queue and return it.
        Returns None if the queue is empty.

        Returns:
            The next node from the queue or None if empty
        """
        if not self.queue:
            logger.warning("Queue is empty, no next active node available")
            return None

        # Synchronize active_node with tree.active if there are discrepancies
        if self.tree and self.active_node != self.tree.active:
            logger.warning(
                "Synchronizing active_node: QueueManager (%s) vs. Tree (%s)",
                self.active_node.id if self.active_node else "None",
                self.tree.active.id if self.tree.active else "None",
            )
            self.active_node = self.tree.active

        # If active node is an irrelevant answer node, remove it
        if (
            self.active_node
            and self.active_node.get_label() == NodeLabel.IRRELEVANT_ANSWER
            and self.active_node_unchanged_count < self.MAX_UNCHANGED_COUNT
        ):
            self.tree.remove_irrelevant_node()
            # Synchronize active_node with tree.active
            self.active_node = self.tree.active

        next_node = self.queue.pop(0)
        self._set_active_node(next_node)
        logger.info(f"Next active node: {next_node.get_label().value}")
        return next_node

    def get_active_node_unchanged_count(self) -> int:
        """
        Returns the count of how many times the active node has remained unchanged.

        Returns:
            Count of unchanged active node
        """
        return self.active_node_unchanged_count

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert queue state to a dictionary for serialization.

        Returns:
            Dictionary representation of the queue state
        """
        return {
            "queue": [n.to_dict() for n in self.queue],
            "active_node": self.active_node.to_dict() if self.active_node else None,
            "active_node_unchanged_count": self.active_node_unchanged_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], tree_instance) -> "QueueManager":
        """
        Create a QueueManager from a dictionary representation.

        Args:
            data: Dictionary representation of queue state
            tree_instance: Tree instance to associate with this queue

        Returns:
            Initialized QueueManager instance
        """
        instance = cls()
        instance.tree = tree_instance

        # Restore queue based on IDs (don't parse again!)
        # (now UUID string)
        instance.queue = []
        for node_data in data.get("queue", []):
            node_id = node_data["id"] 
            node_in_tree = tree_instance.get_node_by_id(node_id)
            if node_in_tree:
                instance.queue.append(node_in_tree)
            else:
                logger.error(f"COULD NOT FIND NODE: {node_id} INSIDE TREE")

        # Set active node (also by ID)
        active_node_data = data.get("active_node")
        if active_node_data:
            node_id = active_node_data["id"]
            node_in_tree = tree_instance.get_node_by_id(node_id)
            if node_in_tree:
                instance._set_active_node(node_in_tree)
            else:
                logger.error(f"UNABLE TO RECONSTRUCT NODE: {node_id} FROM TREE")

        instance.active_node_unchanged_count = data.get("active_node_unchanged_count", 0)
        return instance
