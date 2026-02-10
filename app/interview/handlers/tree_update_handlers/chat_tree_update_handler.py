"""
Tree Update Manager for the Interview Engine.
Manages updating the interview tree with analyzed messages.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree as InterviewTree
from app.interview.interview_tree.tree_utils import TreeUtils
from app.interview.handlers.tree_update_handlers.base_tree_handler import BaseTreeHandler

logger = logging.getLogger(__name__)

# Configuration flags
PRINT_TREE_JSON = False


class TreeUpdateManager(BaseTreeHandler):
    """
    Manages the updating of the interview tree with analyzed messages.
    """

    def __init__(self, tree: InterviewTree):
        super().__init__(tree)
        # Import handlers here to avoid circular imports
        from app.interview.handlers.tree_update_handlers.irrelevant_node_handler import IrrelevantNodeHandler
        from app.interview.handlers.tree_update_handlers.similar_node_handler import SimilarNodeHandler
        
        self.irrelevant_handler = IrrelevantNodeHandler(tree)
        self.similar_handler = SimilarNodeHandler(tree)

    def update_tree_with_analysis(self, label: NodeLabel, summary: str, is_first_message: bool,
                                  parent_node: Optional[Node] = None,
                                  interaction_id: Optional[int] = None) -> Optional[Node]:
        """
        Updates the tree with the analysis results.

        Args:
            label: The NodeLabel for the new node
            summary: The summary for the new node
            is_first_message: Flag whether it's the first message
            parent_node: Optional - An explicit parent node for the new node
            interaction_id: Optional - The ID of the associated chat interaction

        Returns:
            The newly created node or None in case of error
        """
        # Save original active node
        original_active_node = self.tree.active

        if original_active_node.get_label() == NodeLabel.IRRELEVANT_ANSWER and label != NodeLabel.IRRELEVANT_ANSWER:
            return self.irrelevant_handler.transform_irrelevant_node(original_active_node, label, summary,
                                                   is_first_message, interaction_id, parent_node)

        # Special handling for IRRELEVANT_ANSWER
        if label == NodeLabel.IRRELEVANT_ANSWER:
            return self.irrelevant_handler.handle_irrelevant_answer(summary, is_first_message, interaction_id)

        # Use explicit parent node if specified
        if parent_node:
            logger.info(f"Using explicit parent node: {parent_node.id} - {parent_node.get_label().value}")
        else:
            # Normal parent node search
            parent_node = self.find_parent_node(
                label, is_first_message, original_active_node)

            if not parent_node:
                parent_node = self.create_intermediate_nodes(
                    label, original_active_node)

            # Fallback to original active node
            if not parent_node and original_active_node:
                parent_node = original_active_node

        return self.create_and_add_node(parent_node, label, summary, is_first_message, interaction_id)

    # Delegation methods to handlers
    
    async def find_existing_similar_node(self, label: NodeLabel, summary: str, client=None, model=None, topic=None, stimulus=None) -> Tuple[Optional[Node], bool]:
        """
        Finds an existing similar node.

        Returns:
            Tuple (node, is_duplicate_to_ignore):
            - The found node or None
            - Flag whether it is a duplicate that should be ignored
        """
        return await self.similar_handler.find_existing_similar_node(label, summary, client, model, topic, stimulus)
        
    def add_existing_node_as_child(self, new_node: Node, label: NodeLabel = None, parent_node: Optional[Node] = None):
        """
        Adds an existing node as a child of a semantically matching parent node,
        with support for creating intermediate nodes if necessary.
        """
        return self.similar_handler.add_existing_node_as_child(new_node, label, parent_node)