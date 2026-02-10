"""
Interface definitions for message handling components.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional, Callable, Protocol

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.chat_state.chat_state_handler import InterviewStage


class StateManager(Protocol):
    """Protocol for state management functionality."""

    def get_stage(self) -> InterviewStage:
        """Get the current interview stage."""
        ...

    def set_stage(self, stage: InterviewStage) -> None:
        """Set the interview stage."""
        ...


class QueueManager(Protocol):
    """Protocol for queue management functionality."""

    def add_to_queue(self, node_obj: Node) -> None:
        """Add a node to the queue."""
        ...

    def update_unchanged_count(self, found_required_element: bool) -> None:
        """Update the counter for unchanged active node."""
        ...

    def should_move_to_next_node(self) -> bool:
        """Check if we should move to the next node in the queue."""
        ...

    def get_next_active_node(self) -> Optional[Node]:
        """Get the next active node from the queue."""
        ...


class TreeAccess(Protocol):
    """Protocol for tree access functionality."""

    @property
    def active(self) -> Optional[Node]:
        """Get the active node in the tree."""
        ...

    def get_nodes_by_label(self, label: NodeLabel) -> List[Node]:
        """Get nodes by label."""
        ...

    def set_active_node(self, node: Node) -> None:
        """Set the active node."""
        ...

    def remove_irrelevant_node(self) -> None:
        """Remove the irrelevant node."""
        ...
