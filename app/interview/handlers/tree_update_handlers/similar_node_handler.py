"""
Handler for similar nodes in the interview tree.
Manages finding similar nodes and adding them as children.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree as InterviewTree
from app.interview.handlers.tree_update_handlers.base_tree_handler import BaseTreeHandler

logger = logging.getLogger(__name__)


class SimilarNodeHandler(BaseTreeHandler):
    """
    Handles operations related to similar nodes in the tree.
    """

    async def find_existing_similar_node(self, label: NodeLabel, summary: str, client=None, model=None, topic=None, stimulus=None) -> Tuple[Optional[Node], bool]:
        """
        Finds an existing similar node.

        Returns:
            Tuple (node, is_duplicate_to_ignore):
            - The found node or None
            - Flag whether it is a duplicate that should be ignored
        """
        if not self.tree:
            return None, False

        # Read only, do not change
        active_parent = self.tree.active if self.tree.active else None
        return await self.tree.find_similar_node(label, summary, active_parent, client=client, model=model, topic=topic, stimulus=stimulus)

    def add_existing_node_as_child(self, new_node: Node, label: NodeLabel = None, parent_node: Optional[Node] = None):
        """
        Adds an existing node as a child of a semantically matching parent node,
        with support for creating intermediate nodes if necessary.
        """
        # Save the originally active node
        original_active = self.tree.active

        # Determine the label, if not specified
        if label is None and new_node:
            label = new_node.get_label()

        # Special case: Backward relationship ATTRIBUTE to CONSEQUENCE
        if original_active and original_active.get_label() == NodeLabel.CONSEQUENCE and label == NodeLabel.ATTRIBUTE:
            logger.info(
                f"Backward relationship detected: Consequence {original_active.id} → Attribute {new_node.id}")
            # Save the backward relationship in the consequence
            original_active.add_backwards_relation(new_node)

        if original_active and original_active.get_label() == NodeLabel.ATTRIBUTE and label == NodeLabel.ATTRIBUTE:
            logger.info(
                f"Backward relationship detected: Attribute {original_active.id} → Attribute {new_node.id}")
            # Save the backward relationship in the consequence
            original_active.add_backwards_relation(new_node)
        if original_active and label == NodeLabel.ATTRIBUTE:
            logger.info(
                f"Same attribute node {new_node.id} found, save A in IDEA relationship as backward relation for reconstruction")
            self.tree.get_nodes_by_label(
                NodeLabel.IDEA)[-1].add_backwards_relation(new_node)

        is_first_message = False
        # If an explicit parent node was specified, use it
        if parent_node:
            logger.info(
                f"Using explicit parent node: {parent_node.id} - {parent_node.get_label().value}")
        else:
            # Normal parent node finding process
            # Use the active node as starting point
            parent_node = self.find_parent_node(
                label, is_first_message, self.tree.active)

            # If no matching parent node found, try creating intermediate nodes
            if not parent_node:
                parent_node = self.create_intermediate_nodes(
                    label, self.tree.active)

            # Fallback to the active node or root
            if not parent_node:
                parent_node = self.tree.active or self.tree.get_tree_root()

            logger.info(
                f"Chosen parent node for sharing: {parent_node.id} - {parent_node.get_label().value}")

        # Prevent self-loops (node cannot be its own child)
        if parent_node and parent_node.id == new_node.id:
            logger.warning(
                f"Self-loop prevented: Node {new_node.id} cannot be added as its own child")
            return None

        # Check for direct parent-child relationship (avoid direct duplicates)
        if parent_node and (new_node in parent_node.get_children() or parent_node in new_node.get_parents()):
            logger.warning(
                f"Node {new_node.id} is already a child of {parent_node.id} - no action required")
            return None

        # Check if new_node is already an ancestor of parent_node (would create cycle)
        if parent_node and self.tree.is_ancestor_of(new_node, parent_node):
            logger.warning(
                f"Cycle avoidance: Node {new_node.id} is already an ancestor of {parent_node.id}")
            logger.warning(f"Adding would create a cycle in the tree")
            return None

        if parent_node:
            # Set active node to the parent node
            self.tree.active = parent_node

            # Create bidirectional link (parent-child relationship)
            parent_node.add_child(new_node)
            logger.info(
                f"Node {new_node.id} successfully shared as child of {parent_node.id}")

            # Restore active node
            self.tree.active = original_active

            # Output information if the node has multiple parents
            if len(new_node.get_parents()) > 1:
                parent_info = ", ".join(
                    [f"{parent.id}({parent.get_label().value})" for parent in new_node.get_parents()])
                logger.info(
                    f"Node {new_node.id} with multiple parents: now has {len(new_node.get_parents())} parents: [{parent_info}]")

            return new_node
        else:
            logger.warning(
                "No parent node found or specified - no action performed")
            return None