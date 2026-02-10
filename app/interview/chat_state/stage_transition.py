"""
Stage Transitions for the Interview Engine.
Defines rules for valid state transitions in the interview process.
"""

import logging
from typing import Optional, List, Dict, Any

from app.interview.interview_tree.node import Node
from app.interview.interview_tree.node_label import NodeLabel
from app.interview.chat_state.chat_state_handler import InterviewStage

logger = logging.getLogger(__name__)


class StageTransitions:
    """
    Manages transitions between interview stages.
    """

    # Define valid transitions between stages
    VALID_TRANSITIONS = {
        InterviewStage.INITIAL: [InterviewStage.ASKING_FOR_IDEA],
        
        InterviewStage.ASKING_FOR_IDEA: [
            InterviewStage.ASKING_FOR_ATTRIBUTES,
            InterviewStage.COMPLETE
        ],
        
        InterviewStage.ASKING_FOR_ATTRIBUTES: [
            InterviewStage.ASKING_FOR_CONSEQUENCES,
            InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES,
            InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES_TOO_SHORT,
            InterviewStage.COMPLETE,
            InterviewStage.VALUES_LIMIT_REACHED
        ],
        
        InterviewStage.ASKING_FOR_CONSEQUENCES: [
            InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES,
            InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES,
            InterviewStage.COMPLETE,
            InterviewStage.VALUES_LIMIT_REACHED
        ],
        
        InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES: [
            InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES,
            InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES,
            InterviewStage.COMPLETE,
            InterviewStage.VALUES_LIMIT_REACHED
        ],
        
        InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES: [
            InterviewStage.ASKING_FOR_ATTRIBUTES,
            InterviewStage.COMPLETE,
            InterviewStage.VALUES_LIMIT_REACHED,
            InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES_TOO_SHORT
        ],

        InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES_TOO_SHORT: [
            InterviewStage.COMPLETE,
            InterviewStage.VALUES_LIMIT_REACHED,
            InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES,
            InterviewStage.ASKING_AGAIN_FOR_ATTRIBUTES,
        ],
    }

    @classmethod
    def update_interview_stage(cls, state_manager, node_obj: Optional[Node], has_reached_values_limit_func=None) -> None:
        """
        Update the interview stage based on a specific node.
        
        Args:
            state_manager: The state manager to update
            node_obj: The node determining the new stage
            has_reached_values_limit_func: Function to check if values limit is reached
        """
        if node_obj is None:
            # Check if values limit is reached if a function is provided
            if has_reached_values_limit_func and has_reached_values_limit_func():
                state_manager.set_stage(InterviewStage.VALUES_LIMIT_REACHED)
                logger.info("Interview stage: VALUES_LIMIT_REACHED set.")
            else:
                state_manager.set_stage(InterviewStage.COMPLETE)
                logger.info("Interview stage: COMPLETE set.")
        else:
            label = node_obj.get_label()

            if label == NodeLabel.STIMULUS:
                state_manager.set_stage(InterviewStage.ASKING_FOR_IDEA)
                logger.info("Interview stage: ASKING_FOR_IDEA set.")
            elif label == NodeLabel.IDEA:
                state_manager.set_stage(InterviewStage.ASKING_FOR_ATTRIBUTES)
                logger.info("Interview stage: ASKING_FOR_ATTRIBUTES set.")
            elif label == NodeLabel.ATTRIBUTE:
                state_manager.set_stage(InterviewStage.ASKING_FOR_CONSEQUENCES)
                logger.info("Interview stage: ASKING_FOR_CONSEQUENCES set.")
            elif label == NodeLabel.CONSEQUENCE:
                state_manager.set_stage(InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES)
                logger.info("Interview stage: ASKING_FOR_CONSEQUENCES_OR_VALUES set.")

    @classmethod
    def get_next_stage(cls, current_stage: InterviewStage, node_label: Optional[NodeLabel] = None, 
                      values_limit_reached: bool = False) -> InterviewStage:
        """
        Get the next stage based on the current stage and node label.
        
        Args:
            current_stage: The current interview stage
            node_label: The label of the currently active node
            values_limit_reached: Whether the values limit has been reached
            
        Returns:
            The next interview stage
        """
        if values_limit_reached:
            logger.info(f"Values limit reached, transitioning from {current_stage.value} to VALUES_LIMIT_REACHED")
            return InterviewStage.VALUES_LIMIT_REACHED
            
        if not node_label:
            logger.info(f"No node label provided, ending interview from {current_stage.value}")
            return InterviewStage.COMPLETE
            
        # Default transitions based on node label
        if node_label == NodeLabel.STIMULUS:
            return InterviewStage.ASKING_FOR_IDEA
        elif node_label == NodeLabel.IDEA:
            return InterviewStage.ASKING_FOR_ATTRIBUTES
        elif node_label == NodeLabel.ATTRIBUTE:
            return InterviewStage.ASKING_FOR_CONSEQUENCES
        elif node_label == NodeLabel.CONSEQUENCE:
            return InterviewStage.ASKING_FOR_CONSEQUENCES_OR_VALUES
        
        # If no specific rule applies, stay in the current stage if possible
        # or transition to COMPLETE as a safe default
        if current_stage in cls.VALID_TRANSITIONS:
            logger.info(f"No specific transition rule for {node_label} from {current_stage.value}, staying in current stage")
            return current_stage
        else:
            logger.warning(f"No valid transition from {current_stage.value} with {node_label}, defaulting to COMPLETE")
            return InterviewStage.COMPLETE

    @classmethod
    def is_valid_transition(cls, from_stage: InterviewStage, to_stage: InterviewStage) -> bool:
        """
        Check if a transition from one stage to another is valid.
        
        Args:
            from_stage: The starting stage
            to_stage: The target stage
            
        Returns:
            True if the transition is valid
        """
        if from_stage not in cls.VALID_TRANSITIONS:
            logger.warning(f"No defined transitions from {from_stage.value}")
            return False
            
        if to_stage in cls.VALID_TRANSITIONS[from_stage]:
            return True
        
        logger.warning(f"Invalid transition from {from_stage.value} to {to_stage.value}")
        return False