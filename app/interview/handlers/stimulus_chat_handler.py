from typing import Any, List, Dict, Optional

from app.interview.handlers.chat_queue_handler import QueueManager
from app.interview.chat_state.chat_state_handler import InterviewStateManager, InterviewStage
from app.interview.handlers.message_handling.chat_message_handler import MessageProcessingManager
from app.interview.questioning.question_generator import QuestionGenerationManager
from app.interview.interview_tree.tree import Tree
from app.interview.interview_tree.tree_utils import TreeUtils
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.node import Node
from app.interview.handlers.message_handling.factory import MessageProcessorFactory
from app.interview.questioning.llm_response_handler import ResponseHandler
from app.interview.data.interview_data_store import InterviewDataStore
from app.interview.analysis.values_detector import ValuesDetector

import logging

logger = logging.getLogger(__name__)


class StimulusChatHandler:

    DEBUG_TREE = True  # Set to True to enable tree debugging for the backend tree

    def __init__(self, topic: str, stimulus: str, session_id: str, stimuli: Optional[list] = None,
                 n_values_max: int = -1, max_retries: int = 3, min_nodes: Optional[int] = 0) -> None:
        self.topic = topic
        self.stimulus = stimulus
        self.session_id = session_id
        self.stimuli = stimuli if stimuli is not None else []

        self.n_values_max = n_values_max  # -1 means unlimited
        self.max_retries = max_retries    # Default is 3
        self.min_nodes = min_nodes

    def _initialize_new(self) -> None:
        """Initialize the interview tree and all other attributes"""

        self.tree = None
        self.queue_manager = QueueManager()
        self.queue_manager.init_new()

        # Initialize state_manager earlier
        self.state_manager = InterviewStateManager()
        self.state_manager.init_new()

        # Set max_retries in QueueManager with special handling for -1 (unlimited)
        if hasattr(self, 'max_retries'):
            if self.max_retries == -1:
                # Unlimited retries: Set to a very high value
                self.queue_manager.MAX_UNCHANGED_COUNT = 999999  # Practically unlimited
                logger.info("MAX_UNCHANGED_COUNT set to unlimited (max_retries=-1)")
            elif self.max_retries > 0:
                self.queue_manager.MAX_UNCHANGED_COUNT = self.max_retries
                logger.info(f"MAX_UNCHANGED_COUNT set to {self.max_retries} (from max_retries)")
            else:
                # Fallback: at least 3 retries
                self.max_retries = 3
                self.queue_manager.MAX_UNCHANGED_COUNT = 3
                logger.info(f"MAX_UNCHANGED_COUNT set to 3 (minimum limit from max_retries={self.max_retries})")

        # Initialize additional attributes
        self.chat_history: List[Dict[str, Any]] = []
        self.is_finished: bool = False
        self._asked_again_for_attributes = False
        logger.info("Flag '_asked_again_for_attributes' initially set to False")
        self.start_stimulus_id: Optional[str] = None  # UUID string

        try:
            # Root node (STIMULUS) uses UUID id internally
            partial_tree_root = Node(NodeLabel.STIMULUS, self.stimulus)
            self.tree = Tree(partial_tree_root)
            self.queue_manager.set_tree(self.tree)
            self.queue_manager.initialize_stimuli_queue([partial_tree_root])
            self.state_manager.set_stage(InterviewStage.ASKING_FOR_IDEA)
            # Store the ID (UUID string) of the start stimulus
            self.start_stimulus_id = partial_tree_root.id
            logger.info(f"Initialized stimulus root: id={self.start_stimulus_id}, content='{self.stimulus}'")
        except Exception as e:
            self.tree = None
            self.start_stimulus_id = None
            logger.error(f"Error creating tree: {e}")
            logger.error(e, exc_info=True)

        # Initialize message_processor and question_generator
        self.message_processor = MessageProcessingManager(self.tree)
        self.question_generator = QuestionGenerationManager(
            self.tree, self.topic, self.stimulus, self.queue_manager, self.state_manager
        )
        
        # Initialize message processor component
        self.message_processor_component = MessageProcessorFactory.create_from_stimulus_chat_handler(self)

    async def nextInput(self, message: str, client: Any, model: str, template_vars: Dict[str, Any] = None) -> Dict[str, Any]:
        self.state_manager.increment_message_count()
        user_message_index = len(self.chat_history)

        if self.state_manager.is_first_message():
            # For the first user message, always reference the actual stimulus node UUID
            user_node_ids: List[str] = [self.start_stimulus_id] if self.start_stimulus_id else []

            self.chat_history.append({
                "role": "user",
                "content": message,
                "node_ids": user_node_ids
            })

            # Store the current question and answer in the database
            last_question = self.chat_history[-2]["content"] if len(
                self.chat_history) >= 2 else ""
            interaction_id = await self._store_interaction(last_question, message)

            logger.info("First message: Skipping analysis and asking directly for IDEAS about the stimulus")
            self.state_manager.set_stage(InterviewStage.ASKING_FOR_IDEA)
            response = await self._generate_response(client, model, template_vars)

            # System answer: same node IDs as for the user message (UUIDs)
            current_node_ids = user_node_ids.copy()
            self.chat_history.append({
                "role": "system",
                "content": response["Next"]['NextQuestion'],
                "node_ids": current_node_ids
            })

            # Update the user message with the stimulus node ID
            self.chat_history[user_message_index]["node_ids"] = current_node_ids.copy()

            self.is_finished = response["Next"]["EndOfInterview"]
            return response
        else:
            user_node_ids: List[str] = []
            self.chat_history.append({
                "role": "user",
                "content": message,
                "node_ids": user_node_ids
            })

            # Store the current question and answer in the database
            last_question = self.chat_history[-2]["content"] if len(
                self.chat_history) >= 2 else ""
            interaction_id = await self._store_interaction(last_question, message)

        # Pass the interaction ID to the message processor
        topic_switch_info = await self._process_message_content(message, client, model, interaction_id)

        # If topic_switch_info is set, add it to template_vars
        if topic_switch_info:
            if template_vars is None:
                template_vars = {}
            template_vars["topic_switch_info"] = topic_switch_info

        response = await self._generate_response(client, model, template_vars)

        # --- Robust: Collect all affected node IDs for this message (new, merged, referenced) ---
        relevant_node_ids: List[str] = []
        if hasattr(self.message_processor, 'all_nodes_last_message') and self.message_processor.all_nodes_last_message:
            for n in self.message_processor.all_nodes_last_message:
                if hasattr(n, 'id') and n.id not in relevant_node_ids:
                    # n.id is already a UUID string
                    relevant_node_ids.append(n.id)
        # Fallback: if none found but active node exists
        if not relevant_node_ids and self.tree and self.tree.active:
            relevant_node_ids.append(self.tree.active.id)

        # System answer: same node IDs as for the user message (UUIDs)
        self.chat_history.append({
            "role": "system",
            "content": response["Next"]['NextQuestion'],
            "node_ids": relevant_node_ids.copy()
        })
        # Update the user message with the relevant node IDs
        self.chat_history[user_message_index]["node_ids"] = relevant_node_ids.copy()
        self.is_finished = response["Next"]["EndOfInterview"]
        self._log_response(response)
        return response

    async def _store_interaction(self, system_question: str, user_answer: str) -> Optional[int]:
        """Store a chat interaction in the database and return the ID."""
        # Get or create a chat session
        chat_session_id = await InterviewDataStore.get_or_create_chat_session(self.session_id)

        if not chat_session_id:
            logger.warning("No chat session available - cannot store interaction")
            return None

        # Store the interaction
        return await InterviewDataStore.store_interaction(chat_session_id, system_question, user_answer)

    async def _process_message_content(self, message: str, client: Any, model: str, interaction_id: Optional[int] = None) -> None:
        """Process the content of a message using the MessageProcessor component."""
        return await self.message_processor_component.process_message_content(message, client, model, self.min_nodes, interaction_id)

    def _has_reached_values_limit(self) -> bool:
        """Check if the values limit has been reached."""
        return ValuesDetector.has_reached_values_limit(self.tree, self.n_values_max)

    
    async def _generate_response(self, client: Any, model: str, template_vars: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a response based on the current state."""
        logger.debug("Starting _generate_response")
    
        # CRITICAL: Values limit has ABSOLUTE priority - check both conditions
        has_limit = self._has_reached_values_limit()
        has_flag = getattr(self, '_values_limit_just_reached', False)
    
        logger.debug(f"VALUES LIMIT checks: has_limit={has_limit}, has_flag={has_flag}")
    
        # If EITHER criterion is met, IMMEDIATELY return a values limit response
        if has_limit or has_flag:
            logger.info("VALUES LIMIT detected in _generate_response - sending EndOfInterview=True")
    
            # Reset flag for future calls
            if has_flag:
                logger.debug("Resetting _values_limit_just_reached flag")
                delattr(self, '_values_limit_just_reached')
    
            # CRITICAL: Create values limit response and return directly
            logger.info("Creating VALUES LIMIT RESPONSE")
            current_values = ValuesDetector.count_values(self.tree)
            values_response = ResponseHandler.create_values_limit_response(
                tree=self.tree,
                n_values_max=self.n_values_max,
                current_values=current_values,
                stimulus=self.stimulus
            )
    
            # Check response completeness
            if "Next" in values_response and "CompletionReason" in values_response["Next"]:
                logger.info(f"Response contains CompletionReason: {values_response['Next']['CompletionReason']}")
            else:
                logger.error("ERROR: CompletionReason missing in response!")
    
            # Return immediately - NO further code is executed
            return values_response
    
        # NORMAL CASE (no values limit reached)
        # Initialize template variables if none were provided
        template_vars_for_prompt = {} if template_vars is None else template_vars.copy()
    
        # Add values information
        values_info = {
            "current_values_count": ValuesDetector.count_values(self.tree),
            "max_values_limit": self.n_values_max if self.n_values_max and self.n_values_max > 0 else None,
            "values_limit_reached": False  # Definitely False here
        }
        template_vars_for_prompt.update(values_info)
    
        # Generate normal question - template selection now happens in QuestionGenerationManager
        logger.info("Generating normal question - NO values limit")
        response = await self.question_generator.generate_question(
            client=client,
            messages=self.chat_history,
            model=model,
            template_vars=template_vars_for_prompt
        )
    
        # For normal responses: Ensure values info is correct
        if isinstance(response.get("Next"), dict):
            if "ValuesCount" not in response["Next"]:
                response["Next"]["ValuesCount"] = values_info["current_values_count"]
            if "ValuesMax" not in response["Next"]:
                response["Next"]["ValuesMax"] = values_info["max_values_limit"]
            if "ValuesReached" not in response["Next"]:
                response["Next"]["ValuesReached"] = values_info["values_limit_reached"]
    
            # SAFETY: Catch race condition - if limit reached during question generation
            if self._has_reached_values_limit():
                logger.warning("RACE CONDITION: Values limit reached during question generation!")
                current_values = ValuesDetector.count_values(self.tree)
                return ResponseHandler.create_values_limit_response(
                    tree=self.tree,
                    n_values_max=self.n_values_max,
                    current_values=current_values,
                    stimulus=self.stimulus
                )
    
        return response
    
    def _log_response(self, response: Dict[str, Any]) -> None:
        """Log the generated response."""
        ResponseHandler.log_response(response)

    def to_dict(self) -> Dict[str, Any]:
        # Normalize node_ids to strings defensively for persistence
        normalized_history: List[Dict[str, Any]] = []
        for msg in self.chat_history:
            if isinstance(msg, dict):
                m = dict(msg)
                if "node_ids" in m and isinstance(m["node_ids"], list):
                    m["node_ids"] = [str(x) for x in m["node_ids"] if x is not None]
                normalized_history.append(m)
            else:
                normalized_history.append(msg)

        return {
            "topic": self.topic,
            "stimulus": self.stimulus,
            "session_id": self.session_id,
            "n_values_max": self.n_values_max,
            "max_retries": self.max_retries,
            "queue_manager": self.queue_manager.to_dict() if self.queue_manager else None,
            "state_manager": self.state_manager.to_dict() if self.state_manager else None,
            "chat_history": normalized_history,
            "tree": TreeUtils.to_dict(self.tree) if self.tree else None,
            "active_node_id": self.tree.active.id if self.tree and self.tree.active else None,
            "message_count": self.state_manager.message_count if self.state_manager else 0,
            "content_message_count": self.state_manager.content_message_count if self.state_manager else 0,
            "is_finished": self.is_finished,
            "asked_again_for_attributes": getattr(self, '_asked_again_for_attributes', False),
            "min_nodes": self.min_nodes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StimulusChatHandler":
        n_values_max = data.get("n_values_max", -1)
        # Default is 3 if not present
        max_retries = data.get("max_retries", 3)

        min_nodes = data.get("min_nodes", 0)

        handler = cls(
            topic=data["topic"],
            stimulus=data["stimulus"],
            session_id=data["session_id"],
            n_values_max=n_values_max,
            max_retries=max_retries,
            stimuli=data.get("stimuli", []),
            min_nodes=min_nodes
        )
        handler.is_finished = data.get("is_finished", False)

        handler._asked_again_for_attributes = data.get(
            "asked_again_for_attributes", False)

        from app.interview.interview_tree.tree import Tree as InterviewTree
        handler.tree = TreeUtils.from_dict(
            data["tree"]) if data.get("tree") else None

        # Ensure QueueManager uses correct max_retries value
        handler.queue_manager = QueueManager.from_dict(
            data["queue_manager"], handler.tree)
        # Special handling for max_retries
        if hasattr(handler, 'max_retries'):
            if handler.max_retries == -1:
                # Unlimited retries
                handler.queue_manager.MAX_UNCHANGED_COUNT = 999999
            elif handler.max_retries > 0:
                handler.queue_manager.MAX_UNCHANGED_COUNT = handler.max_retries

        handler.state_manager = InterviewStateManager.from_dict(
            data["state_manager"])

        # Load and normalize chat_history (convert any legacy int IDs to strings)
        handler.chat_history = list(data.get("chat_history", []))
        for msg in handler.chat_history:
            if isinstance(msg, dict) and "node_ids" in msg and isinstance(msg["node_ids"], list):
                msg["node_ids"] = [str(x) for x in msg["node_ids"] if x is not None]

        handler.message_processor = MessageProcessingManager(handler.tree)
        handler.question_generator = QuestionGenerationManager(
            handler.tree, handler.topic, handler.stimulus, handler.queue_manager, handler.state_manager
        )
        
        # Initialize message processor component
        handler.message_processor_component = MessageProcessorFactory.create_from_stimulus_chat_handler(handler)

        # Ensure start_stimulus_id is properly set (important for restoration)
        handler.start_stimulus_id = None
        if handler.tree and handler.tree.root and hasattr(handler.tree.root, 'id'):
            handler.start_stimulus_id = handler.tree.root.id

        return handler
