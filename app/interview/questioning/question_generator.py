"""
Question Generation Manager for the Interview Engine.
Manages question generation based on the current interview state.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.interview_tree.tree import Tree as InterviewTree
from app.interview.interview_tree.tree_utils import TreeUtils
from app.interview.handlers.chat_queue_handler import QueueManager
from app.interview.chat_state.chat_state_handler import InterviewStateManager, InterviewStage
from app.llm.template_store import render_template
from app.llm.utils import clean_json_response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db as get_async_session
from app.db.models_chat import ChatInteraction
from app.interview.questioning.llm_response_handler import ResponseHandler
from app.interview.interview_tree.tree_utils import TreeUtils

logger = logging.getLogger(__name__)


class QuestionGenerationManager:
    """
    Manages question generation based on the current interview state.
    """
    
    # Template name constants for better readability and organization
    TEMPLATE_STANDARD = "queue_laddering"
    TEMPLATE_ASK_AGAIN_ATTRIBUTES = "ask_again_for_attributes"
    TEMPLATE_EXPANDED_IDEA = "expanded_idea_question"
    TEMPLATE_EXPANDED_ATTRIBUTE = "expanded_attribute_question"
    TEMPLATE_EXPANDED_CONSEQUENCE = "expanded_consequence_question"
    TEMPLATE_EXPANDED_VALUE = "expanded_value_question"
    
    # Map question types to their corresponding templates
    QUESTION_TYPE_TO_TEMPLATE = {
        "ask_again_for_attributes": TEMPLATE_ASK_AGAIN_ATTRIBUTES,
        "expanded_idea_question": TEMPLATE_EXPANDED_IDEA,
        "expanded_attribute_question": TEMPLATE_EXPANDED_ATTRIBUTE,
        "expanded_consequence_question": TEMPLATE_EXPANDED_CONSEQUENCE,
        "expanded_value_question": TEMPLATE_EXPANDED_VALUE,
        # Standard types use the default template
        "Idea": TEMPLATE_STANDARD,
        "A1.1": TEMPLATE_STANDARD,
        "C1.1": TEMPLATE_STANDARD,
        "CV1.1": TEMPLATE_STANDARD,
    }

    def __init__(self, tree: InterviewTree, topic: str, stimulus: str, queue_manager: QueueManager, state_manager: InterviewStateManager):
        self.tree = tree
        self.topic = topic
        self.stimulus = stimulus
        self.queue_manager = queue_manager
        self.state_manager = state_manager

    async def generate_question(self, client: Any, messages: List[Dict[str, str]], model: str,
                                template_name: str = None,
                                template_vars: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generates a question based on the current interview state.
        
        Args:
            client: LLM client
            messages: Message history
            model: LLM model to use
            template_name: Optional override for template selection
            template_vars: Additional template variables
            
        Returns:
            Dictionary with the generated question and related data
        """
        try:
            active_node = self.tree.active if self.tree else None
            active_label = active_node.get_label() if active_node else None

            logger.debug(f"Generating question: active_node={active_node.id if active_node else None}, "
                         f"label={active_label}, interview_stage={self.state_manager.get_stage_value()}")

            next_question_type = self._determine_next_question_type(
                active_node, active_label, self.state_manager, self.queue_manager
            )

            if next_question_type == "END OF INTERVIEW":
                logger.info(
                    "Interview end detected - sending EndOfInterview=True to frontend")
                return ResponseHandler.create_end_of_interview_response(self.tree)

            # Check for topic switch info
            topic_switch_info = None
            if template_vars and "topic_switch_info" in template_vars:
                topic_switch_info = template_vars.pop("topic_switch_info")
                logger.debug(
                    f"Topic switch detected: Switching to {topic_switch_info['new_node_type']}")

            # Determine the template to use based on question type
            # If template_name is provided, use it as an override
            if template_name is None:
                template_name = self.get_template_for_question_type(next_question_type)
                logger.debug(f"Selected template '{template_name}' for question type '{next_question_type}'")

            # Generate question
            response = await self._generate_llm_question(
                client, messages, model, active_node, next_question_type,
                self.queue_manager, self.state_manager, template_name, template_vars
            )

            # Handle topic switch
            if topic_switch_info and "Next" in response and "NextQuestion" in response["Next"]:
                transition_text = self._generate_topic_transition_text(
                    topic_switch_info)
                original_question = response["Next"]["NextQuestion"]
                response["Next"]["NextQuestion"] = f"{transition_text}\n\n{original_question}"
                response["Next"]["TopicSwitchReason"] = "max_attempts_reached"

            # Add values information to response
            if template_vars and isinstance(response.get("Next"), dict):
                values_count = template_vars.get("current_values_count")
                values_max = template_vars.get("max_values_limit")
                values_reached = template_vars.get(
                    "values_limit_reached", False)

                if values_count is not None:
                    response["Next"]["ValuesCount"] = values_count
                if values_max is not None:
                    response["Next"]["ValuesMax"] = values_max
                response["Next"]["ValuesReached"] = values_reached

                # Set CompletionReason only for normal interview end
                if response["Next"].get("EndOfInterview") and not values_reached:
                    response["Next"]["CompletionReason"] = "INTERVIEW_COMPLETE"

            return response

        except Exception as e:
            logger.exception(f"Error in question generation: {e}")
            return ResponseHandler.create_error_response(str(e), self.tree, self.stimulus)
            
    def get_template_for_question_type(self, question_type: str) -> str:
        """
        Returns the appropriate template name for the given question type.
        
        Args:
            question_type: Type of question (e.g., "Idea", "A1.1", "expanded_idea_question")
            
        Returns:
            Template name to use
        """
        # Look up in the mapping dictionary, defaulting to standard template
        return self.QUESTION_TYPE_TO_TEMPLATE.get(question_type, self.TEMPLATE_STANDARD)

    def _generate_topic_transition_text(self, topic_switch_info: Dict[str, Any]) -> str:
        """
        Generates an explanatory text for topic switching.

        Args:
            topic_switch_info: Dictionary with topic switch information

        Returns:
            Formatted explanation text
        """
        reason = topic_switch_info.get("reason")

        if reason == "max_attempts_reached":
            # Truncate long contents
            previous_content = topic_switch_info.get(
                "previous_node_content", "")
            new_type = topic_switch_info.get("new_node_type", "").lower()
            new_content = topic_switch_info.get("new_node_content", "")

            if len(previous_content) > 30:
                previous_content = previous_content[:27] + "..."
            if len(new_content) > 30:
                new_content = new_content[:27] + "..."

            # Base message
            base_message = "Unfortunately, we weren't able to get a meaningful response to this question and the maximum number of attempts has been reached. Therefore, "

            # Generate text based on NodeLabel values
            if new_type == NodeLabel.ATTRIBUTE.value.lower():
                return f"{base_message}let's try to explore the following different feature you mentioned:"
            elif new_type == NodeLabel.CONSEQUENCE.value.lower():
                return f"{base_message}let's now talk about a different aspect in this context you mentioned."
            else:
                return f"{base_message}let's now talk about another point:"

        # Generic text for other reasons
        return "Let's shift our focus to another aspect of this topic."

    def _create_end_of_interview_response(self) -> Dict[str, Any]:
        """
        Creates a response signaling the end of the interview.

        This response contains the EndOfInterview=True flag, which is recognized by the frontend
        to mark the chat as finished and update the UI accordingly.
        """
        return {
            "Next": {
                "NextQuestion": "Thank you very much for your participation in this interview so far! Your insights about this topic have been valuable and provided us with all the information we need. If you notice any other open chat discussions for different stimuli, please complete those as well to finish the entire interview process.",
                "AskingIntervieweeFor": "END OF INTERVIEW",
                "ThoughtProcess": "Interview completed, no more stimuli to discuss",
                "EndOfInterview": True
            },
            "Chains": TreeUtils.format_chains_for_response(self.tree),
            "Tree": json.loads(TreeUtils.to_json(self.tree)) if self.tree else None
        }

    def _determine_next_question_type(self, active_node: Optional[Node],
                                      active_label: Optional[NodeLabel],
                                      state_manager: InterviewStateManager,
                                      queue_manager: QueueManager) -> str:
        """Determines the next question type based on the current state."""
        # If no active node is available, check the queue
        if state_manager.is_complete():
            logger.info(
                "Interview completion initiated - no active node and no stimuli in queue")
            return "END OF INTERVIEW"

        if state_manager.get_stage() == InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES:
            logger.debug("Interview phase: Asking again for attributes")
            return "ask_again_for_attributes"
        
        if state_manager.get_stage() == InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES_TOO_SHORT:
            logger.debug("Interview phase: Asking again for attributes even more")
            return "asking_again_for_attributes_too_short"

        # Check if the active node has remained unchanged (unchanged_count >= 1)
        unchanged_count = 0
        if queue_manager:
            logger.debug(
                "Checking for unchanged nodes in queue for question generation")
            unchanged_count = queue_manager.get_active_node_unchanged_count()

        # For unchanged normal nodes or irrelevant answers: Use advanced questioning strategy
        if unchanged_count >= 1 or active_label == NodeLabel.IRRELEVANT_ANSWER:
            logger.debug(
                f"Using advanced question strategy: Unchanged answers ({unchanged_count}) or irrelevant message")
            return self._handle_with_advanced_strategy(active_node, state_manager, queue_manager)

        # Standard processing based on node label
        if active_label == NodeLabel.STIMULUS:
            state_manager.set_stage(InterviewStage.ASKING_FOR_IDEA)
            return "Idea"
        elif active_label == NodeLabel.IDEA:
            state_manager.set_stage(InterviewStage.ASKING_FOR_ATTRIBUTES)
            return "A1.1"
        elif active_label == NodeLabel.ATTRIBUTE:
            state_manager.set_stage(InterviewStage.ASKING_FOR_CONSEQUENCES)
            return "C1.1"
        elif active_label == NodeLabel.CONSEQUENCE:
            state_manager.set_stage(
                InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES)
            return "CV1.1"
        elif active_label == NodeLabel.VALUE:
            # Error handling for unexpected VALUE node
            error_msg = f"Error: VALUE node detected as active node (ID: {active_node.id if active_node else 'None'}), which should not happen"
            logger.error(error_msg)

            state_manager.set_stage(InterviewStage.PROCESSING_NEXT_CONSEQUENCE)
            return "next_consequence"

        return "unknown"

    def _handle_with_advanced_strategy(self, active_node: Node, state_manager: InterviewStateManager, queue_manager: QueueManager) -> str:
        """
        Applies advanced questioning strategies for irrelevant answers or unchanged normal nodes.

        This method generates special question types designed to extract relevant ACV elements
        through alternative questioning techniques when the user is stuck on a topic or giving
        irrelevant answers.
        """
        label = active_node.get_label()
        node_id = active_node.id if active_node else "None"

        is_irrelevant = label == NodeLabel.IRRELEVANT_ANSWER

        logger.debug(
            f"Using advanced question strategy for {'irrelevant' if is_irrelevant else 'unchanged'} node: {node_id}")

        # Determine counter for repeated irrelevant answers
        counter = 1
        if is_irrelevant:
            dummy_context = active_node.get_conclusion() or ""
            counter = self._extract_counter_from_dummy_context(dummy_context)
            logger.debug(f"Irrelevant answers counter: {counter}")
        else:
            # For normal nodes: Use the unchanged count directly
            if queue_manager:
                counter = queue_manager.get_active_node_unchanged_count()
                logger.debug(f"Unchanged answers counter: {counter}")

        # If it's an irrelevant node, use its parent node to determine question strategy
        if is_irrelevant:
            parent_nodes = active_node.get_parents()
            if parent_nodes:
                parent_label = parent_nodes[0].get_label()
                return self._select_strategy_for_label(parent_label, state_manager)

        # For normal nodes, directly use the label
        return self._select_strategy_for_label(label, state_manager)

    def _select_strategy_for_label(self, label: NodeLabel, state_manager: InterviewStateManager) -> str:
        """
        Selects an advanced question strategy based on the label.

        Args:
            label: The NodeLabel for which to select the strategy
            state_manager: The state manager for interview phases

        Returns:
            The selected question type
        """

        if label == NodeLabel.STIMULUS:
            state_manager.set_stage(InterviewStage.ASKING_FOR_IDEA)
            return "expanded_idea_question"
        elif label == NodeLabel.IDEA:
            state_manager.set_stage(InterviewStage.ASKING_FOR_ATTRIBUTES)
            return "expanded_attribute_question"
        elif label == NodeLabel.ATTRIBUTE:
            state_manager.set_stage(InterviewStage.ASKING_FOR_CONSEQUENCES)
            return "expanded_consequence_question"
        elif label == NodeLabel.CONSEQUENCE:
            state_manager.set_stage(
                InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES)
            return "expanded_value_question"
        elif label == NodeLabel.VALUE:
            state_manager.set_stage(
                InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES)
            return "expanded_value_question"

    def _extract_counter_from_dummy_context(self, dummy_context: str) -> int:
        """
        Extracts the counter from a dummy context string.

        Args:
            dummy_context: The context string of the dummy node

        Returns:
            Counter value (default: 1)
        """
        try:
            # Check for "Total: X" format (for shortened stacked conclusions)
            if "(Total:" in dummy_context:
                total_part = dummy_context.split(
                    "(Total:")[-1].strip().rstrip(")")
                return int(total_part)

            # Count STACK entries - each STACK entry is an irrelevant answer
            if "STACK-" in dummy_context:
                stack_count = dummy_context.count("STACK-")
                return stack_count + 1  # +1 for the original irrelevant answer

            # Fallback: Check DUMMY-X format
            if "DUMMY-" in dummy_context:
                dummy_part = dummy_context.split("DUMMY-")[1].split(":")[0]
                return int(dummy_part)

        except (ValueError, IndexError):
            pass

        return 1  # Default counter

    async def _generate_llm_question(self, client: Any, messages: List[Dict[str, str]],
                                   model: str, active_node: Optional[Node],
                                   next_question_type: str, queue_manager: QueueManager,
                                   state_manager: InterviewStateManager,
                                   template_name: str, template_vars: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates the actual question using the LLM with standardized structured output handling.
        
        This method processes context, prepares the prompt with appropriate templates,
        and calls the LLM using provider-agnostic structured output handling.
        
        Args:
            client: LLM client instance (provider-specific)
            messages: Message history for context
            model: Model identifier to use
            active_node: Active node in the interview tree
            next_question_type: Type of question to generate (determines template)
            queue_manager: Queue manager for node processing
            state_manager: State manager for interview phases
            template_name: Base template name for question generation
            template_vars: Additional template variables
        
        Returns:
            Dictionary with the generated question and related data
        """
        # Build context path for active node
        current_path = TreeUtils.build_context_path_from_node(self.tree, active_node)
        
        logger.debug(f"Generating LLM question for node {active_node.id if active_node else 'None'}, "
                     f"conclusion: {active_node.get_conclusion() if active_node else 'None'}, "
                     f"path: {current_path}")
        
        # Get relevant interactions from the tree path
        branch_interactions = await self._get_branch_interactions(active_node)
        
        # Determine relevant last response for context
        relevant_last_response = ""
        if branch_interactions and branch_interactions[0]["user_answer"]:
            relevant_last_response = branch_interactions[0]["user_answer"]
            logger.debug(
                f"Using relevant last response from trace: {relevant_last_response[:50]}...")
        else:
            relevant_last_response = messages[-1]['content'] if messages else ""
            logger.debug(
                f"Using relevant last response from messages: {relevant_last_response[:50]}...")
        
        # Prepare prompt variables with the relevant last response
        prompt_vars = self._prepare_prompt_vars(
            active_node, current_path, state_manager,
            messages, template_vars, relevant_last_response
        )
        
        # Add specific template variables based on the question type
        # This replaces the old _configure_template_for_question_type functionality
        self._add_question_type_specific_vars(
            next_question_type, prompt_vars, branch_interactions, messages
        )
        
        # Generate system prompt from template
        logger.info(f"Using template: {template_name}")
        system_prompt = render_template(template_name, **prompt_vars)
        
        # Prepare messages with branch-specific interactions
        question_messages = [{"role": "system", "content": system_prompt}]
        
        # Special case: For ask_again_for_attributes, use only system prompt
        if next_question_type == self.TEMPLATE_ASK_AGAIN_ATTRIBUTES:
            logger.debug("ask_again_for_attributes: Using system prompt only without additional context")
        else:
            # Normal behavior: Add contextual conversation history
            if branch_interactions:
                logger.debug(f"Using {len(branch_interactions[:3])} branch interactions as context")
        
                # Add up to 3 interactions in chronological order (oldest first)
                interactions_to_add = branch_interactions[:3]
        
                for interaction in reversed(interactions_to_add):
                    # Add system question followed by user answer
                    question_messages.append({
                        "role": "assistant", 
                        "content": interaction["system_question"]
                    })
                    question_messages.append({
                        "role": "user",
                        "content": interaction["user_answer"]
                    })
        
            elif messages:
                # Fallback: Use recent messages from conversation history
                logger.debug("Using general message history (up to 3 messages)")
                question_messages.extend(messages[-3:])
        
        logger.debug(f"Final context message count: {len(question_messages)}")
        
        # Initialize LLM client
        from app.llm.client import LlmClient
        llm_client = LlmClient(client, model)
        
        # Define JSON schema for structured output validation
        # This matches the structure expected in the templates
        json_schema = {
            "type": "object",
            "properties": {
                "Next": {
                    "type": "object",
                    "properties": {
                        "NextQuestion": {"type": "string"},
                        "AskingIntervieweeFor": {"type": "string"},
                        "ThoughtProcess": {"type": "string"},
                        "EndOfInterview": {"type": "boolean"}
                    },
                    "required": ["NextQuestion", "ThoughtProcess"]
                }
            },
            "required": ["Next"]
        }
        
        try:
            # Call LLM with structured output handling
            # Note: We don't set temperature here - it will be handled by query_with_structured_output
            # based on provider-specific optimal settings
            response_content = await llm_client.query_with_structured_output(
                messages=question_messages,
                schema=json_schema,
                temperature=0.3  # Lower temperature for more consistent analysis
            )
            
            logger.debug("LLM structured output request successful")
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise e
        
        # Parse, validate, and format the response
        response = ResponseHandler.parse_and_validate_response(
            response_content, next_question_type, queue_manager, self.tree, self.stimulus)
        
        return response

    def _add_question_type_specific_vars(self, next_question_type: str, prompt_vars: Dict[str, Any],
                                         branch_interactions: List[Dict[str, Any]],
                                         messages: List[Dict[str, str]]) -> None:
        """
        Adds question type specific variables to the prompt vars.
        
        Args:
            next_question_type: The type of question to generate
            prompt_vars: Dictionary with prompt variables (modified in-place)
            branch_interactions: List of branch interactions
            messages: Chat message history
        """
        # Special handling for ask_again_for_attributes
        if next_question_type == "ask_again_for_attributes":
            logger.debug(f"Adding specific variables for {self.TEMPLATE_ASK_AGAIN_ATTRIBUTES}")

            # Collect all previously discussed attributes
            discussed_attributes = []
            if self.tree:
                attribute_nodes = self.tree.get_nodes_by_label(
                    NodeLabel.ATTRIBUTE)
                discussed_attributes = [
                    attr_node.get_conclusion()
                    for attr_node in attribute_nodes
                    if attr_node.get_conclusion() and not attr_node.get_conclusion().startswith(("AUTO:", "DUMMY-"))
                ]

            # Format the attribute list for the template
            if discussed_attributes:
                attributes_text = "\n".join(
                    [f"- {attr}" for attr in discussed_attributes])
            else:
                attributes_text = "- No specific attributes have been identified yet"

            # Additional template variables for ask_again_for_attributes
            prompt_vars.update({
                "discussed_attributes": attributes_text
            })

        # Handling for expanded question types
        elif next_question_type in ["expanded_idea_question", "expanded_attribute_question", 
                                   "expanded_consequence_question", "expanded_value_question"]:
            logger.debug(f"Adding specific variables for {next_question_type}")

            # Additional variables for extended templates
            last_question = ""
            if branch_interactions and len(branch_interactions) > 0:
                last_question = branch_interactions[0]["system_question"]
            else:
                last_question = messages[-2]['content'] if len(
                    messages) > 1 else ""

            prompt_vars.update({
                "target_element_type": self._get_target_element_type(next_question_type),
                "last_question": last_question,
            })

    async def _get_branch_interactions(self, active_node: Optional[Node]) -> List[Dict[str, Any]]:
        """
        Retrieves the chat interactions for the current branch of the tree,
        from the active node up to the idea or stimulus.

        Args:
            active_node: The active node

        Returns:
            List of chat interactions, sorted from newest (active node) to oldest
        """
        if not active_node:
            return []

        # Collect all nodes in the path from the active node to the root
        path_nodes = []
        current = active_node

        # Go back at most to the idea node or stimulus
        while current:
            path_nodes.append(current)

            # Stop at idea or stimulus
            if current.get_label() in [NodeLabel.IDEA, NodeLabel.STIMULUS]:
                break

            # Go to the latest parent node (with highest ID)
            parent = current.get_latest_parent()
            if not parent:
                break
            current = parent

        # Collect all interaction IDs from the trace_explanation_elements of the nodes
        interactions_data = []

        logger.debug(
            f"Collecting interactions for {len(path_nodes)} nodes in tree path")

        # Collect all interaction IDs
        interaction_ids = []
        node_map = {}  # Mapping of interaction ID to node ID

        for node_obj in path_nodes:
            # Go through trace elements of the node
            trace_elements = node_obj.trace if hasattr(
                node_obj, 'trace') else []

            for trace_elem in trace_elements:
                if hasattr(trace_elem, 'get_interaction_id') and trace_elem.get_interaction_id():
                    interaction_id = trace_elem.get_interaction_id()
                    interaction_ids.append(interaction_id)
                    node_map[interaction_id] = node_obj.id

        # If no interactions were found
        if not interaction_ids:
            logger.warning("No interaction IDs found in trace elements")
            return []

        try:
            # Get database session
            async for session in get_async_session():
                # Retrieve all relevant chat interactions at once
                # Sort by created_at DESC for newest first
                stmt = select(ChatInteraction).where(
                    ChatInteraction.id.in_(interaction_ids)
                ).order_by(ChatInteraction.created_at.desc())  # Newest first

                result = await session.execute(stmt)
                interactions = result.scalars().all()

                # Convert interactions to a simple format
                for interaction in interactions:
                    interactions_data.append({
                        "id": interaction.id,
                        "node_id": node_map.get(interaction.id),
                        "system_question": interaction.system_question,
                        "user_answer": interaction.user_answer,
                        "created_at": interaction.created_at
                    })
        except Exception as e:
            logger.error(f"Error retrieving chat interactions: {e}")
            # Return empty list on errors
            return []

        logger.debug(
            f"Retrieved {len(interactions_data)} chat interactions for tree path (newest first)")
        return interactions_data

    def _get_target_element_type(self, question_type: str) -> str:
        """
        Determines the target element type based on the question type.

        Args:
            question_type: The type of extended question

        Returns:
            The corresponding element type
        """
        mapping = {
            "expanded_idea_question": "Idea",
            "expanded_attribute_question": "Attribute",
            "expanded_consequence_question": "Consequence",
            "expanded_value_question": "Consequence or Value",
        }
        return mapping.get(question_type, "Unknown")


    def _prepare_prompt_vars(self, active_node: Optional[Node], current_path: str,
                             state_manager: InterviewStateManager,
                             messages: List[Dict[str, str]], template_vars: Dict[str, Any],
                             relevant_last_response: str = None) -> Dict[str, Any]:
        """
        Prepares the prompt variables.

        Args:
            active_node: The active node
            current_path: The formatted current path
            state_manager: The state manager
            messages: The chat messages
            template_vars: Additional template variables
            relevant_last_response: Optional - The relevant last response from the tree path

        Returns:
            Dictionary with prompt variables
        """
        # Determine the parent node of the active node (if available)
        parent_node = active_node.get_latest_parent(
        ) if active_node and active_node.get_parents() else None
        parent_context = f"{parent_node.get_label().value}: {parent_node.get_conclusion()}" if parent_node else "None"

        # Determine relevant context of the last response
        last_user_response = ""

        # Prioritize the passed relevant response from the tree path
        if relevant_last_response:
            last_user_response = relevant_last_response
        # Fall back to the last message
        elif messages:
            last_user_response = messages[-1]["content"]

        prompt_vars = {
            "topic": self.topic or "Unspecified topic",
            "active_stimulus": self.stimulus or "Unspecified stimulus",
            "active_node_label": active_node.get_label().value if active_node else "None",
            "active_node_content": active_node.get_conclusion() if active_node else "None",
            "current_path": current_path,
            "interview_stage": state_manager.get_stage_value(),
            "last_user_response": last_user_response,
            "parent_context": parent_context
        }

        # Merge with additional template variables
        if template_vars:
            for key, value in template_vars.items():
                if key not in prompt_vars:
                    prompt_vars[key] = value

        return prompt_vars