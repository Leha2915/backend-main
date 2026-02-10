"""
Interview State Manager for the Interview Engine.
Manages the current state of the interview and state transitions.
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel

logger = logging.getLogger(__name__)


class InterviewStage(Enum):
    """Enum for the different interview phases."""
    INITIAL = "initial"
    ASKING_FOR_IDEA = "asking_for_idea"
    ASKING_FOR_ATTRIBUTES = "asking_for_attributes"
    ASKING_FOR_CONSEQUENCES = "asking_for_consequences"
    ASKING_FOR_CONSEQUENCES_OR_VALUES = "asking_for_consequences_or_values"
    ASKING_AGAIN_FOR_ATTRIBUTES = "asking_again_for_attributes"
    ASKING_AGAIN_FOR_ATTRIBUTES_TOO_SHORT = "asking_again_for_attributes_too_short"
    RECEIVED_ATTRIBUTES = "received_attributes"
    RECEIVED_CONSEQUENCES = "received_consequences"
    RECEIVED_VALUES = "received_values"
    PROCESSING_NEXT_CONSEQUENCE = "processing_next_consequence"
    COMPLETE = "complete"
    # Specific stage for values limit
    VALUES_LIMIT_REACHED = "values_limit_reached"
    NO_STIMULI = "no_stimuli"


class InterviewStateManager:
    """
    Manages the current state of the interview and determines the next steps.
    """

    def __init__(self):
        """Initialize with default values."""
        self.init_new()

    def init_new(self):
        """Initialize a new interview state."""
        self.stage = InterviewStage.INITIAL
        self.message_count = 0
        self.content_message_count = 0

    def increment_message_count(self) -> None:
        """Increment the message counter."""
        self.message_count += 1
        logger.debug(f"Message count incremented to {self.message_count}")

    def increment_content_message_count(self) -> None:
        """Increment the content message counter."""
        self.content_message_count += 1
        logger.debug(f"Content message count incremented to {self.content_message_count}")

    def is_first_message(self) -> bool:
        """Check if this is the first message."""
        return self.message_count == 1

    def set_stage(self, stage: InterviewStage) -> None:
        """Explicitly set the interview stage."""
        logger.info(f"Interview stage changed from {self.stage.value} to {stage.value}")
        self.stage = stage

    def get_stage(self) -> InterviewStage:
        """Get the current interview stage."""
        return self.stage

    def get_stage_value(self) -> str:
        """Get the string value of the current stage."""
        return self.stage.value

    def is_complete(self) -> bool:
        """Check if the interview is completed."""
        return self.stage == InterviewStage.COMPLETE

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization."""
        return {
            "stage": self.stage.value,
            "message_count": self.message_count,
            "content_message_count": self.content_message_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterviewStateManager":
        """Create an InterviewStateManager from a dictionary."""
        instance = cls()
        try:
            instance.stage = InterviewStage(data.get("stage", "initial"))
        except ValueError:
            logger.warning(f"Invalid stage value: {data.get('stage')}. Defaulting to INITIAL.")
            instance.stage = InterviewStage.INITIAL

        instance.message_count = data.get("message_count", 0)
        instance.content_message_count = data.get("content_message_count", 0)
        return instance