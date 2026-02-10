"""
Node Analysis Component for the Interview Engine.
Provides specialized analysis of nodes created during message processing.
"""

import logging
from typing import Any, List, Dict, Optional, Tuple

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree_utils import TreeUtils
from app.interview.handlers.message_handling.interfaces import TreeAccess

logger = logging.getLogger(__name__)


class NodeAnalyzer:
    """
    Analyzes nodes created from user messages and determines their relationships.
    """

    @staticmethod
    def has_real_nodes(nodes: List[Node]) -> bool:
        """
        Check if there are any non-irrelevant nodes in the list.

        Args:
            nodes: List of nodes to check

        Returns:
            True if there are non-irrelevant nodes
        """
        return any(
            node.get_label() != NodeLabel.IRRELEVANT_ANSWER
            for node in nodes
        )

    @staticmethod
    def extract_value_nodes(nodes: List[Node]) -> List[Node]:
        """
        Extract VALUE nodes from a list of nodes.

        Args:
            nodes: List of nodes to check

        Returns:
            List of VALUE nodes
        """
        return [
            node for node in nodes
            if node.get_label() == NodeLabel.VALUE
        ]

    @staticmethod
    def check_for_required_elements(tree: TreeAccess, created_nodes: List[Node]) -> bool:
        """
        Check if required elements based on the active node were found.

        Args:
            tree: Tree access object
            created_nodes: List of newly created nodes

        Returns:
            True if required elements were found, False otherwise
        """
        if not created_nodes:
            logger.info("No new node created - e.g., due to merging")
            if tree.active:
                logger.warning(f"Staying with active node: {tree.active.id}")
            return False

        active_node = tree.active
        if not active_node:
            return False

        active_label = active_node.get_label()
        received_labels = [node_obj.get_label() for node_obj in created_nodes]

        # Case 1: IDEA -> ATTRIBUTE (extended logic)
        if active_label == NodeLabel.IDEA:
            if NodeLabel.ATTRIBUTE in received_labels:
                # Primary condition satisfied: ATTRIBUTE after IDEA found
                logger.info("ATTRIBUTE after IDEA found - can continue")
                return True
            else:
                # Fallback for IDEA: Check if at least one CONSEQUENCE/VALUE is an indirect child of the IDEA
                consequence_value_nodes = [
                    node_obj for node_obj in created_nodes
                    if node_obj.get_label() in [NodeLabel.CONSEQUENCE, NodeLabel.VALUE]
                ]

                for node_obj in consequence_value_nodes:
                    if TreeUtils.is_direct_or_indirect_child(active_node, node_obj):
                        logger.info(
                            f"{node_obj.get_label().value} node {node_obj.id} is indirect child of active IDEA {active_node.id} - can continue")
                        return True

        # Case 2: ATTRIBUTE -> CONSEQUENCE (extended logic)
        elif active_label == NodeLabel.ATTRIBUTE:
            # Only consider C nodes that are actually connected with the active A
            connected_consequences = [
                node_obj for node_obj in created_nodes
                if node_obj.get_label() == NodeLabel.CONSEQUENCE and
                TreeUtils.is_direct_or_indirect_child(active_node, node_obj)
            ]

            if connected_consequences:
                logger.info(
                    f"{len(connected_consequences)} CONSEQUENCE(S) connected with active ATTRIBUTE found - can continue")
                return True
            else:
                # Fallback for ATTRIBUTE: Check if at least one VALUE is an indirect child of the ATTRIBUTE
                value_nodes = [
                    node_obj for node_obj in created_nodes
                    if node_obj.get_label() == NodeLabel.VALUE
                ]
                for node_obj in value_nodes:
                    if TreeUtils.is_direct_or_indirect_child(active_node, node_obj):
                        logger.info(
                            f"{node_obj.get_label().value} node {node_obj.id} is indirect child of active ATTRIBUTE {active_node.id} - can continue")
                        return True

        # Case 3: CONSEQUENCE -> VALUE/CONSEQUENCE (extended logic)
        elif active_label == NodeLabel.CONSEQUENCE:
            # Only consider C nodes and V nodes that are actually connected with the active C
            connected_consequences = [
                node_obj for node_obj in created_nodes
                if node_obj.get_label() == NodeLabel.CONSEQUENCE and
                TreeUtils.is_direct_or_indirect_child(active_node, node_obj)
            ]

            connected_values = [
                node_obj for node_obj in created_nodes
                if node_obj.get_label() == NodeLabel.VALUE and
                TreeUtils.is_direct_or_indirect_child(active_node, node_obj)
            ]

            if connected_consequences or connected_values:
                consequence_count = len(connected_consequences)
                value_count = len(connected_values)

                if consequence_count > 0 and value_count > 0:
                    logger.info(
                        f"{consequence_count} CONSEQUENCE(S) and {value_count} VALUE(S) connected with active CONSEQUENCE found - can continue")
                elif consequence_count > 0:
                    logger.info(
                        f"{consequence_count} CONSEQUENCE(S) connected with active CONSEQUENCE found - can continue")
                elif value_count > 0:
                    logger.info(
                        f"{value_count} VALUE(S) connected with active CONSEQUENCE found - can continue")
                return True

        # Case 4: IRRELEVANT_ANSWER
        elif active_label == NodeLabel.IRRELEVANT_ANSWER and NodeLabel.IRRELEVANT_ANSWER not in received_labels:
            logger.info("Irrelevant answer processed - can continue")
            return True

        return False
