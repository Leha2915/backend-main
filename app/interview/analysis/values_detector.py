"""
Values Detector for the Interview Engine.
Detects and tracks values in the interview process.
"""

import logging
from typing import Optional

from app.interview.interview_tree.tree import Tree
from app.interview.interview_tree.node_label import NodeLabel

logger = logging.getLogger(__name__)


class ValuesDetector:
    """
    Detects and tracks values in the interview process.
    Manages value limits and provides value-related utilities.
    """

    @staticmethod
    def has_reached_values_limit(tree: Optional[Tree], n_values_max: int) -> bool:
        """
        Check if the values limit has been reached.

        Args:
            tree: The interview tree
            n_values_max: Maximum number of values allowed (-1 for unlimited)

        Returns:
            True if the values limit has been reached, False otherwise
        """
        if not n_values_max or n_values_max <= 0:  # -1 or 0 means unlimited
            return False

        if not tree:
            return False

        value_nodes = tree.get_nodes_by_label(NodeLabel.VALUE)
        current_values = len(value_nodes)
        limit_reached = current_values >= n_values_max

        if limit_reached:
            logger.info(
                f"VALUES LIMIT REACHED: {current_values}/{n_values_max}")
        else:
            logger.info(f"Values status: {current_values}/{n_values_max}")

        return limit_reached

    @staticmethod
    def count_values(tree: Optional[Tree]) -> int:
        """
        Count the number of VALUE nodes in a tree.

        Args:
            tree: The interview tree

        Returns:
            Number of VALUE nodes
        """
        if not tree:
            return 0

        value_nodes = tree.get_nodes_by_label(NodeLabel.VALUE)
        value_count = len(value_nodes)

        logger.info(f"Current VALUE nodes in tree: {value_count}")
        return value_count
