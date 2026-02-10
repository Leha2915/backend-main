"""
Response handling utilities for interview question generation.
Provides methods for parsing LLM responses and creating structured response objects.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from app.interview.handlers.chat_queue_handler import QueueManager
from app.interview.interview_tree.tree_utils import TreeUtils
from app.llm.utils import clean_json_response

logger = logging.getLogger(__name__)

class ResponseHandler:
    """
    Handles LLM response parsing and creates structured response objects
    for different interview scenarios.
    """
    
    @staticmethod
    def parse_and_validate_response(
        response_content: str, 
        next_question_type: str,
        queue_manager: QueueManager,
        tree: Any = None,
        stimulus: str = None
    ) -> Dict[str, Any]:
        """
        Parses and validates the LLM response with robust error handling.
        
        Args:
            response_content: Raw response content from LLM
            next_question_type: Type of question being asked
            queue_manager: Queue manager for the interview
            tree: The interview tree object
            stimulus: The stimulus being discussed
            
        Returns:
            Structured response dictionary
        """
        # Save the original response for error reports
        original_content = response_content

        try:
            # Clean the response before parsing
            cleaned_content = clean_json_response(response_content)

            try:
                # Try to parse
                parsed_data = json.loads(cleaned_content)
            except json.JSONDecodeError as parse_error:
                logger.error(
                    f"JSON parsing still failed after cleaning: {parse_error}")
                logger.debug(
                    f"Cleaned content (problematic): {cleaned_content[:200]}...")
                # Go directly to fallback
                return ResponseHandler.create_fallback_response(
                    next_question_type, 
                    f"JSON parsing error after cleaning: {parse_error}",
                    tree, 
                    stimulus
                )

            # Check if the basic structure is correct
            if not isinstance(parsed_data, dict):
                logger.error(
                    f"Parsed data is not a dictionary: {type(parsed_data)}")
                return ResponseHandler.create_fallback_response(
                    next_question_type, 
                    "Invalid JSON structure",
                    tree, 
                    stimulus
                )

            # Create a new dictionary with only the "Next" object
            result = {"Next": {}, "Chains": []}

            # Extract and validate the "Next" object
            if "Next" in parsed_data and isinstance(parsed_data["Next"], dict):
                next_obj = parsed_data["Next"]

                # Set NextQuestion
                if "NextQuestion" in next_obj:
                    result["Next"]["NextQuestion"] = next_obj["NextQuestion"]
                else:
                    logger.warning("Missing 'NextQuestion' field in response")
                    result["Next"][
                        "NextQuestion"] = f"Could you tell me more about {stimulus or 'this topic'}?"

                # Override AskingIntervieweeFor with the correct value
                result["Next"]["AskingIntervieweeFor"] = next_question_type or "unknown"

                # Use ThoughtProcess if available, otherwise set default
                if "ThoughtProcess" in next_obj:
                    result["Next"]["ThoughtProcess"] = next_obj["ThoughtProcess"]
                else:
                    result["Next"]["ThoughtProcess"] = "Queue-based interview"

                # EndOfInterview is always false, except in special cases
                result["Next"]["EndOfInterview"] = False
            else:
                logger.error("Missing or invalid 'Next' field in response")
                return ResponseHandler.create_fallback_response(
                    next_question_type, 
                    "Invalid Next structure",
                    tree, 
                    stimulus
                )

            # Add Chains (always generated from Tree, never from LLM response)
            result["Chains"] = ResponseHandler.format_chains_for_response(tree)

            # Add Tree structure
            if tree:
                tree_json = TreeUtils.to_json(tree)
                result["Tree"] = json.loads(tree_json)

            return result

        except Exception as e:
            # General error handling as a last resort
            logger.exception(
                f"Unexpected error in parse_and_validate_response: {e}")
            logger.debug(
                f"Original problematic content: {original_content[:200]}...")

            # Direct fallback without throwing exception
            return ResponseHandler.create_fallback_response(
                next_question_type, 
                f"Unexpected error: {e}",
                tree, 
                stimulus
            )

    @staticmethod
    def create_response(
        tree: Any,
        next_question: str,
        next_question_type: str = "fallback",
        thought_process: str = "",
        end_of_interview: bool = False
    ) -> Dict[str, Any]:
        """
        Generic method for creating structured responses.

        Args:
            tree: The interview tree
            next_question: The question to ask
            next_question_type: Type of question (e.g., "fallback", "error_recovery")
            thought_process: Explanation of the thought process
            end_of_interview: Flag indicating whether the interview is ended

        Returns:
            A structured response in the expected format
        """
        return {
            "Next": {
                "NextQuestion": next_question,
                "AskingIntervieweeFor": next_question_type,
                "ThoughtProcess": thought_process,
                "EndOfInterview": end_of_interview
            },
            "Chains": ResponseHandler.format_chains_for_response(tree),
            "Tree": json.loads(TreeUtils.to_json(tree)) if tree else None
        }

    @staticmethod
    def create_fallback_response(
        next_question_type: str, 
        error_reason: str = "",
        tree: Any = None,
        stimulus: str = None
    ) -> Dict[str, Any]:
        """
        Creates a fallback response for internal processing errors.
        
        Args:
            next_question_type: Type of question being asked
            error_reason: Reason for the fallback
            tree: Interview tree
            stimulus: Interview stimulus
            
        Returns:
            Fallback response dictionary
        """
        return ResponseHandler.create_response(
            tree=tree,
            next_question=f"Could you tell me more about your experience with {stimulus or 'this topic'}? I'm particularly interested in what features or aspects you find valuable.",
            next_question_type=next_question_type or "fallback",
            thought_process=f"Error handling: {error_reason}",
            end_of_interview=False
        )

    @staticmethod
    def create_error_response(
        error_message: str,
        tree: Any = None,
        stimulus: str = None
    ) -> Dict[str, Any]:
        """
        Creates an error response.
        
        Args:
            error_message: Error message to include
            tree: Interview tree
            stimulus: Interview stimulus
            
        Returns:
            Error response dictionary
        """
        return ResponseHandler.create_response(
            tree=tree,
            next_question=f"I apologize, but I encountered a problem with the interview structure. Could we continue our discussion about {stimulus or 'this topic'}?",
            next_question_type="error_recovery",
            thought_process=f"Error recovery: {error_message}",
            end_of_interview=False
        )
        
    @staticmethod
    def create_end_of_interview_response(tree: Any = None) -> Dict[str, Any]:
        """
        Creates a response signaling the end of the interview.
        
        Args:
            tree: Interview tree
            
        Returns:
            End of interview response dictionary
        """
        return {
            "Next": {
                "NextQuestion": "Thank you very much for your participation in this interview so far! Your insights about this topic have been valuable and provided us with all the information we need. If you notice any other open chat discussions for different stimuli, please complete those as well to finish the entire interview process.",
                "AskingIntervieweeFor": "END OF INTERVIEW",
                "ThoughtProcess": "Interview completed, no more stimuli to discuss",
                "EndOfInterview": True
            },
            "Chains": ResponseHandler.format_chains_for_response(tree),
            "Tree": json.loads(TreeUtils.to_json(tree)) if tree else None
        }
    
    @staticmethod
    def create_values_limit_response(tree: Any = None, n_values_max: int = 0, current_values: int = 0, stimulus: str = None) -> Dict[str, Any]:
        """
        Creates a special response when the values limit has been reached.
        
        Args:
            tree: Interview tree
            n_values_max: Maximum number of values allowed
            current_values: Current number of values collected
            stimulus: The interview stimulus
            
        Returns:
            Values limit response dictionary
        """
        logger.info(f"Creating VALUES LIMIT RESPONSE: {current_values}/{n_values_max}")

        return {
            "Next": {
                "NextQuestion": f"Thank you for sharing your insights! You have identified {current_values} core values, which reaches our target for this interview. Your responses have provided valuable information about what matters most to you regarding {stimulus}.",
                "AskingIntervieweeFor": "VALUES_LIMIT_REACHED",
                "ThoughtProcess": f"Interview completed due to reaching the maximum values limit of {n_values_max}. The participant has successfully identified {current_values} values.",
                "EndOfInterview": True,
                "ValuesCount": current_values,
                "ValuesMax": n_values_max,
                "ValuesReached": True,
                "CompletionReason": "VALUES_LIMIT_REACHED"
            },
            "Chains": ResponseHandler.format_chains_for_response(tree),
            "Tree": json.loads(TreeUtils.to_json(tree)) if tree else None
        }
    
    @staticmethod
    def format_chains_for_response(tree: Any) -> List[Dict[str, Any]]:
        """
        Formats the chains for the response.
        Delegates to TreeUtils.format_chains_for_response.
        
        Args:
            tree: Interview tree
            
        Returns:
            List of chains in structured format
        """
        if tree is None:
            return []
            
        return TreeUtils.format_chains_for_response(tree)
    
    @staticmethod
    def log_response(response: Dict[str, Any]) -> None:
        """
        Logs information about the generated response.
        
        Args:
            response: The response to log
        """
        if "_log_info" in response:
            info = response["_log_info"]
            logger.info(f"LLM ASKS: '{info['next_question']}' (Asking for: {info['asking_for']})")
            del response["_log_info"]

        if "Next" in response and "NextQuestion" in response["Next"]:
            next_question_type = response["Next"].get(
                "AskingIntervieweeFor", "unknown")
            logger.info(f"Queue-based question generated: '{response['Next']['NextQuestion'][:50]}...' (Asking for: {next_question_type})")