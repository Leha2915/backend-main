"""
Interview Session module for the modular Interview Engine.
Manages the flow of interviews and builds a structured interview tree.
"""

import logging
from typing import Dict, Any, Optional, List

from app.db.models_project import Project
from app.interview.handlers.stimulus_chat_handler import StimulusChatHandler
from app.interview.interview_tree.node import Node as NodeClass

logger = logging.getLogger(__name__)


class InterviewSessionManager:
    """
    Main class for interview session management.
    Coordinates the various manager components for a clean interview system.
    """

    def __init__(self, project_data: Project, session_id: str):
        """
        Initializes an interview session.

        Args:
            project_data: Project data with topic, stimuli, n_values_max and max_retries
            session_id: Unique ID of the interview session
        """
        self.session_id = session_id
        self.topic = project_data.topic
        self.stimuli = project_data.stimuli
        self.chat_session_handlers: List[StimulusChatHandler] = []
        self.is_complete = False
        self.min_nodes = project_data.min_nodes

        # Extract n_values_max from project_data and store
        self.n_values_max = getattr(
            project_data, 'n_values_max', -1)  # -1 = unlimited
        # Extract max_retries from project_data and store
        self.max_retries = getattr(
            project_data, 'max_retries', 3)  # Default value 3

    async def init_chats(self) -> None:
        """Initializes chat sessions for all stimuli."""
        # No global node id counter needed with UUIDs
        for stimulus in self.stimuli:
            handler = StimulusChatHandler(
                self.topic,
                stimulus,
                self.session_id,
                self.stimuli,
                self.n_values_max,
                max_retries=self.max_retries,
                min_nodes=self.min_nodes
            )
            handler._initialize_new()
            self.chat_session_handlers.append(handler)

    def get_chat(self, i: int) -> StimulusChatHandler:
        """
        Returns the chat handler at the given index.

        Args:
            i: Index of the chat handler

        Returns:
            The corresponding chat session handler
        """
        return self.chat_session_handlers[i]

    def get_chat_by_stimulus(self, stimulus: str) -> Optional[StimulusChatHandler]:
        """
        Finds the chat handler for a specific stimulus.

        Args:
            stimulus: Stimulus text

        Returns:
            The matching chat handler or None
        """
        for chat in self.chat_session_handlers:
            if getattr(chat, "stimulus", None) == stimulus:
                return chat
        return None

    def has_started(self, stimulus: str) -> bool:
        """
        Checks if a chat for the given stimulus has already begun.

        Args:
            stimulus: Stimulus text

        Returns:
            True if the chat has already started, False otherwise
        """
        chat = self.get_chat_by_stimulus(stimulus)

        if not chat:
            return False

        if not chat.chat_history:
            return False

        return True

    async def handle_input(self, stimulus: str, message: str,
                           client: Any, model: str,
                           template_vars: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handles user input for a specific stimulus chat.

        Args:
            stimulus: The stimulus text
            message: User input message
            client: LLM client
            model: LLM model name
            template_vars: Optional template variables

        Returns:
            Response dictionary
        """
        logger.info(f"Adding to stimulus: {stimulus[:20]}[...]")

        # Handle input and response
        chat_id = self.stimuli.index(stimulus)
        selected_chat_handler = self.chat_session_handlers[chat_id]

        answer = await selected_chat_handler.nextInput(message, client, model, template_vars)

        return answer

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the handler to a dictionary for storage.

        Returns:
            Dictionary representation of the handler
        """
        json_representation = {
            "session_id": self.session_id,
            "topic": self.topic,
            "stimuli": self.stimuli,
            "n_values_max": self.n_values_max,
            "max_retries": self.max_retries,
            "chat_sessions": [handler.to_dict() for handler in self.chat_session_handlers],
            "min_nodes": self.min_nodes,
        }

        return json_representation

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterviewSessionManager":
        """
        Creates a handler from a stored dictionary.

        Args:
            data: Dictionary with handler data

        Returns:
            New InterviewSession
        """
        # Create project_data with n_values_max and max_retries
        mock_project = Project(
            topic=data["topic"],
            stimuli=data["stimuli"],
            n_values_max=data.get("n_values_max", -1),
            max_retries=data.get("max_retries", 3),
            min_nodes=data.get("min_nodes", 0)
        )

        session = cls(mock_project, data["session_id"])

        # Load ChatSessionHandlers with n_values_max and max_retries
        session.chat_session_handlers = [
            StimulusChatHandler.from_dict({
                **chat_data,
                "n_values_max": session.n_values_max,
                "min_nodes": session.min_nodes,
                "max_retries": session.max_retries
            })
            for chat_data in data.get("chat_sessions", [])
        ]

        return session
