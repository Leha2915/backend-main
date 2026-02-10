"""
Interview Flow Controller for the Interview Engine.
Manages the flow and state transitions of the interview process.
"""

import logging
from typing import Any, List, Dict, Optional, Callable

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.chat_state.chat_state_handler import InterviewStage
from app.interview.chat_state.stage_transition import StageTransitions
from app.interview.handlers.message_handling.interfaces import StateManager, QueueManager, TreeAccess
from app.interview.analysis.values_detector import ValuesDetector

logger = logging.getLogger(__name__)


class InterviewFlowController:
    """
    Controls the flow of the interview process.
    Manages state transitions and interview progression.
    """

    def __init__(self,
                 state_manager: StateManager,
                 queue_manager: QueueManager,
                 tree: TreeAccess,
                 max_retries: int,
                 n_values_max: int,
                 on_values_limit_reached: Callable[[], None],
                 asked_again_for_attributes: bool = False,
                 on_attribute_flag_changed: Optional[Callable[[bool], None]] = None):
        """
        Initialize the interview flow controller.

        Args:
            state_manager: State manager for interview stages
            queue_manager: Queue manager for node progression
            tree: Tree access object
            max_retries: Maximum number of retries for a node
            n_values_max: Maximum number of value nodes
            on_values_limit_reached: Callback for when values limit is reached
        """
        self.state_manager = state_manager
        self.queue_manager = queue_manager
        self.tree = tree
        self.max_retries = max_retries
        self.n_values_max = n_values_max
        self.on_values_limit_reached = on_values_limit_reached
        self._asked_again_for_attributes = asked_again_for_attributes
        self._on_attribute_flag_changed = on_attribute_flag_changed  # Store callback

    def set_asked_again_for_attributes(self, value: bool) -> None:
        """Update the flag and notify parent if callback exists"""
        if self._asked_again_for_attributes != value:
            self._asked_again_for_attributes = value
            # Notify parent object
            if self._on_attribute_flag_changed:
                self._on_attribute_flag_changed(value)

    def _count_nodes(self) -> int:
        try:
            node_ids = set()
            for lbl in NodeLabel:
                try:
                    for n in self.tree.get_nodes_by_label(lbl):
                        if hasattr(n, "id"):
                            node_ids.add(n.id)  # UUID strings work fine in a set
                except Exception:
                    continue
            return len(node_ids)
        except Exception:
            return 0

    def handle_attribute_request_flag(self, has_real_created_nodes: bool, created_nodes: List[Node], min_nodes_required: int) -> bool:
        """
        Handle the attribute request flag.

        Args:
            has_real_created_nodes: Whether real (non-irrelevant) nodes were created
            created_nodes: List of created nodes

        Returns:
            True if interview should end, False otherwise
        """
        if has_real_created_nodes and self._asked_again_for_attributes:
            logger.info(
                "Real nodes created while 'ask_again_for_attributes' - resetting flag to False")
            self.set_asked_again_for_attributes(False)
            return False

        elif not has_real_created_nodes and self._asked_again_for_attributes:

            node_count = self._count_nodes()

            if min_nodes_required and (node_count < min_nodes_required):
                logger.info(
                    f"No real nodes while in 'ask_again_for_attributes', "
                    f"but tree has only {node_count} nodes (< {min_nodes_required}) : keep asking."
                )

                idea_nodes = self.tree.get_nodes_by_label(NodeLabel.IDEA)
                if not idea_nodes:
                    logger.warning("No IDEA node found - ending interview anyway")
                    self.update_interview_stage(None)
                    return True

                idea_node = idea_nodes[0]
                self.queue_manager.add_to_queue(idea_node)
                self.state_manager.set_stage(InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES_TOO_SHORT)
                return False  # Keep digging

            logger.warning(
                "No real nodes created while 'ask_again_for_attributes' - ending interview")

            # Case 1: Find an irrelevant node in created_nodes
            irrelevant_node = next((node_obj for node_obj in created_nodes if
                                    node_obj.get_label() == NodeLabel.IRRELEVANT_ANSWER), None)

            if self.tree and irrelevant_node:
                # Save the current active node
                original_active_node = self.tree.active

                logger.info(
                    f"Removing newly created dummy node (ID: {irrelevant_node.id}) before ending interview")

                # Set the irrelevant node as active
                self.tree.set_active_node(irrelevant_node)

                # Remove the irrelevant node
                self.tree.remove_irrelevant_node()

                # Reset the original active node if available and not removed
                if original_active_node:
                    self.tree.set_active_node(original_active_node)
                    logger.info(
                        f"Active node reset to ID: {original_active_node.id}")

            logger.info(
                "No new attributes found after asking again - ending interview")
            self.update_interview_stage(None)
            return True

        return False

    def handle_queue_progress(self, found_required_element: bool, created_nodes: List[Node]) -> Optional[Dict[str, Any]]:
        """
        Handle progress in the queue - whether to move to the next node.

        Args:
            found_required_element: Whether required elements were found
            created_nodes: List of created nodes

        Returns:
            Optional topic switch information
        """
        # Check if we should move to the next node in the queue
        topic_switch_info = None
        if self.queue_manager.should_move_to_next_node():
            if self.max_retries == -1:
                logger.warning(
                    "Internal retry limit reached (unlimited max_retries) - switching to next node")
            else:
                logger.warning(
                    f"Too many attempts without required element ({self.max_retries}) - switching to next node")

            next_node = self.queue_manager.get_next_active_node()

            # Store information about topic switch for the frontend
            if next_node:
                # Dynamic calculation of displayed attempts
                displayed_attempts = self.max_retries if self.max_retries != -1 else "unlimited"

                active_node = self.tree.active

                topic_switch_info = {
                    "reason": "max_attempts_reached",
                    "attempts": displayed_attempts,  # Show "unlimited" for -1
                    # Raw value for internal use
                    "attempts_raw": self.queue_manager.MAX_UNCHANGED_COUNT,
                    "previous_node_type": active_node.get_label().value if active_node else "None",
                    "previous_node_content": active_node.get_conclusion() if active_node else "None",
                    "new_node_type": next_node.get_label().value,
                    "new_node_content": next_node.get_conclusion()
                }
                self.update_interview_stage(next_node)
            elif next_node is None:
                if not self.try_ask_again_for_attributes_or_end_interview(created_nodes):
                    logger.info("Interview ended after too many attempts")

        # If required element was found, move to the next node
        elif found_required_element and self.tree:
            if self.tree.active and self.tree.active.get_label() == NodeLabel.IDEA:
                # Get the next node from queue (should be the newly added ATTRIBUTE)
                next_node = self.queue_manager.get_next_active_node()
                if next_node:
                    self.update_interview_stage(next_node)
                else:
                    # Check for VALUE nodes in created_nodes
                    has_value_nodes = any(
                        node_obj.get_label() == NodeLabel.VALUE
                        for node_obj in created_nodes
                    )

                    if has_value_nodes:
                        logger.info(
                            "VALUE node found at IDEA stage - asking for more attributes or ending interview")
                        if not self.try_ask_again_for_attributes_or_end_interview(created_nodes):
                            logger.info("Interview ended after VALUE creation")
                    else:
                        # Fallback for other cases (e.g. irrelevant answers)
                        logger.info(
                            "No more nodes in queue - staying with current node")
                        self.update_interview_stage(self.tree.active)
            else:
                next_node = self.queue_manager.get_next_active_node()
                if next_node:
                    self.update_interview_stage(next_node)
                else:
                    if not self.try_ask_again_for_attributes_or_end_interview(created_nodes):
                        logger.info("Interview ended - no more nodes")
        else:
            # Update interview phase based on created nodes
            self.update_interview_stage(self.tree.active)

        # Return topic switch info for response generation (can be None)
        return topic_switch_info

    def try_ask_again_for_attributes_or_end_interview(self, created_nodes: List[Node]) -> bool:
        """
        Check if the interview should end or ask once more for attributes.
        Also considers the values limit.

        Args:
            created_nodes: List of created nodes

        Returns:
            True if interview continues (asking for more attributes)
            False if interview should end
        """
        # Check values limit FIRST
        if self.has_reached_values_limit():
            logger.info(
                "VALUES LIMIT reached - automatically ending interview")
            self.state_manager.set_stage(InterviewStage.VALUES_LIMIT_REACHED)
            return False

        # Existing logic for asked_again_for_attributes
        if not self._asked_again_for_attributes:
            logger.info(
                "Queue is empty, but haven't asked for more attributes yet - asking again for attributes")

            # Find IDEA node in the tree
            idea_nodes = self.tree.get_nodes_by_label(NodeLabel.IDEA)
            if not idea_nodes:
                logger.warning("No IDEA node found - ending interview anyway")
                self.update_interview_stage(None)
                return False

            idea_node = idea_nodes[0]  # Take the first IDEA node

            # Set IDEA as active node
            self.queue_manager.add_to_queue(idea_node)
            logger.info(
                f"IDEA node {idea_node.id} added to queue again: '{idea_node.get_conclusion()}'")

            # Set interview phase to "ask again for attributes"
            self.state_manager.set_stage(
                InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES)

            # Mark that we've already asked for more attributes
            self.set_asked_again_for_attributes(True)
            logger.info("Flag 'asked_again_for_attributes' set to True")

            return True  # Continue interview
        else:

            logger.info(
                "Queue is empty and already asked for more attributes - interview completed!")
            # This sets the phase to COMPLETE
            self.update_interview_stage(None)
            return False  # End interview

    def update_interview_stage(self, node_obj: Optional[Node]) -> None:
        """
        Update the interview stage based on a node.

        Args:
            node_obj: The node determining the new stage
        """
        # Call the StageTransitions class
        StageTransitions.update_interview_stage(
            self.state_manager,
            node_obj,
            has_reached_values_limit_func=self.has_reached_values_limit
        )

    def has_reached_values_limit(self) -> bool:
        """
        Check if the values limit has been reached.

        Returns:
            True if values limit has been reached
        """
        limit_reached = ValuesDetector.has_reached_values_limit(
            self.tree, self.n_values_max)
        if limit_reached:
            self.on_values_limit_reached()
        return limit_reached
