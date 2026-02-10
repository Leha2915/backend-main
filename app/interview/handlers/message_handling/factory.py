"""
Factory for creating message handling components.
"""

from typing import Any, List, Dict, Optional, Callable

from app.interview.handlers.message_handling.message_processor import MessageProcessor


class MessageProcessorFactory:
    """
    Factory for creating MessageProcessor instances.
    """

    @staticmethod
    def create_from_stimulus_chat_handler(handler: Any) -> MessageProcessor:
        """
        Create a MessageProcessor from a StimulusChatHandler instance.

        Args:
            handler: StimulusChatHandler instance

        Returns:
            MessageProcessor instance
        """
        # Define the values limit reached callback
        flag_value = getattr(handler, '_asked_again_for_attributes', False)
        
        def on_values_limit_reached():
            # Set flag for special handling in response generation
            handler._values_limit_just_reached = True
    
        processor = MessageProcessor(
            message_processor=handler.message_processor,
            state_manager=handler.state_manager,
            queue_manager=handler.queue_manager,
            tree=handler.tree,
            max_retries=handler.max_retries,
            n_values_max=handler.n_values_max,
            topic=handler.topic,
            stimulus=handler.stimulus,
            chat_history=handler.chat_history,
            on_values_limit_reached=on_values_limit_reached,
            debug_tree=handler.DEBUG_TREE,
            asked_again_for_attributes=flag_value
        )
        
        # FÜGE DIESE ZEILE HINZU - Setze die Referenz zum Elternobjekt
        processor.message_processor._parent_handler = handler
        
        return processor
