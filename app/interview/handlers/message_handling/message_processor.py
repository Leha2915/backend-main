"""
Message Processing Component for the Interview Engine.
Handles the analysis and processing of user messages during interviews.
"""

import logging
from typing import Any, List, Dict, Optional, Tuple, Callable

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.chat_state.chat_state_handler import InterviewStage
from app.interview.handlers.message_handling.node_analyzer import NodeAnalyzer
from app.interview.handlers.message_handling.interview_flow import InterviewFlowController
from app.interview.handlers.message_handling.interfaces import StateManager, QueueManager, TreeAccess

logger = logging.getLogger(__name__)


class MessageProcessor:
    """
    Processes user messages and manages the interview flow based on content analysis.
    Coordinates the analysis of messages and updates to the interview state.
    """

    def __init__(self, 
                 message_processor: Any,
                 state_manager: StateManager,
                 queue_manager: QueueManager,
                 tree: TreeAccess,
                 max_retries: int,
                 n_values_max: int,
                 topic: str,
                 stimulus: str,
                 chat_history: List[Dict[str, Any]],
                 on_values_limit_reached: Callable[[], None] = lambda: None,
                 debug_tree: bool = True,
                 asked_again_for_attributes: bool = False):
        
        
        
        """
        Initialize the message processor with required services.
        
        Args:
            message_processor: Component that processes raw messages into nodes
            state_manager: Manager for interview state
            queue_manager: Manager for node queue
            tree: Tree access object
            max_retries: Maximum number of retries
            n_values_max: Maximum number of values
            topic: Interview topic
            stimulus: Interview stimulus
            chat_history: Chat history list
            on_values_limit_reached: Callback when values limit is reached
            debug_tree: Whether to output debug information about the tree
        """
        self.message_processor = message_processor
        self.state_manager = state_manager
        self.queue_manager = queue_manager
        self.tree = tree
        self.topic = topic
        self.stimulus = stimulus
        self.chat_history = chat_history
        self.debug_tree = debug_tree
        
        # Last created nodes for reference
        self._last_created_nodes = []

        # Define callback function to update parent
        def update_parent_flag(value: bool) -> None:
            # Update the flag in the StimulusChatHandler
            if hasattr(message_processor, '_parent_handler') and message_processor._parent_handler:
                message_processor._parent_handler._asked_again_for_attributes = value
        
        # Create the flow controller
        self.flow_controller = InterviewFlowController(
            state_manager=state_manager,
            queue_manager=queue_manager,
            tree=tree,
            max_retries=max_retries,
            n_values_max=n_values_max,
            on_values_limit_reached=on_values_limit_reached,
            asked_again_for_attributes=asked_again_for_attributes,
            on_attribute_flag_changed=update_parent_flag
        )
        
    async def process_message_content(self, message: str, client: Any, model: str, min_nodes_required: int,
                                    interaction_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Process message content and update the interview state accordingly.
        
        Args:
            message: User message
            client: LLM client
            model: LLM model name
            interaction_id: Optional database ID of the interaction
            
        Returns:
            Optional topic switch information
        """
        # Check if this is the first content message
        is_first_content_message = self.state_manager.get_stage() == InterviewStage.ASKING_FOR_IDEA

        if is_first_content_message:
            logger.info("Detected: Interview phase is ASKING_FOR_IDEA - treating as first content message")

        # Process message with interaction ID
        previous_question = self.chat_history[-2]["content"] if self.chat_history else None
        
        created_nodes = await self.message_processor.process_message(
            message, client, model, is_first_content_message,
            previous_question, 
            self.topic, self.stimulus, interaction_id
        )

        # Store created nodes for later reference
        self._last_created_nodes = created_nodes

        # Process the created nodes and update interview state
        return await self._handle_created_nodes(created_nodes, min_nodes_required)

    async def _handle_created_nodes(self, created_nodes: List[Node], min_nodes_required: int) -> Optional[Dict[str, Any]]:
        """
        Process created nodes and update interview state accordingly.
        
        Args:
            created_nodes: List of newly created nodes
            
        Returns:
            Optional topic switch information
        """
        # Check for created nodes outside of IRRELEVANT_ANSWER
        has_real_created_nodes = NodeAnalyzer.has_real_nodes(created_nodes)

        # Check for newly created VALUE nodes
        new_value_nodes = NodeAnalyzer.extract_value_nodes(created_nodes)

        if new_value_nodes:
            logger.info(f"Created {len(new_value_nodes)} new VALUE nodes")

            # Check values limit after creating new VALUE nodes
            if self.flow_controller.has_reached_values_limit():
                logger.info("VALUES LIMIT reached after VALUE creation - ending interview")
                if self.tree and self.tree.active and self.tree.active.get_label() == NodeLabel.IRRELEVANT_ANSWER:
                    self.tree.remove_irrelevant_node()
                self.flow_controller.update_interview_stage(None)
                return None

        # Handle attribute request flag
        if self.flow_controller.handle_attribute_request_flag(has_real_created_nodes, created_nodes, min_nodes_required):
            return None

        # Check if required elements were found based on active node
        found_required_element = NodeAnalyzer.check_for_required_elements(self.tree, created_nodes)

        # Update the counter for unchanged active node
        self.queue_manager.update_unchanged_count(found_required_element)

        # Update queues
        for node_obj in created_nodes:
            self.queue_manager.add_to_queue(node_obj)

        # Check if we should move to the next node in the queue
        topic_switch_info = self.flow_controller.handle_queue_progress(found_required_element, created_nodes)
            
        # Debug Tree state
        if self.debug_tree and self.tree:
            from app.interview.interview_tree.tree_utils import TreeUtils
            TreeUtils.debug_tree(self.tree, logger)
            
        # Return topic switch info for _generate_response (can be None)
        return topic_switch_info
        
