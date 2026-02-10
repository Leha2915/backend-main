"""
Data access layer for the Interview Engine.
Manages database operations for interviews.
"""

import logging
from typing import Optional

from app.db.session import get_db
from app.db.models_chat import ChatSession, ChatInteraction
from sqlalchemy import select

logger = logging.getLogger(__name__)


class InterviewDataStore:
    """
    Data access layer for interview data.
    Handles database operations for chat sessions and interactions.
    """

    @staticmethod
    async def get_or_create_chat_session(interview_session_id: str) -> Optional[str]:
        """
        Get or create a ChatSession for an interview session.

        Args:
            interview_session_id: The ID of the interview session

        Returns:
            ID of the chat session or None if creation failed
        """
        try:
            async for session in get_db():
                # Check if a ChatSession already exists for this interview session
                stmt = select(ChatSession).where(
                    ChatSession.interview_session_id == interview_session_id
                )
                result = await session.execute(stmt)
                chat_session = result.scalars().first()

                if not chat_session:
                    # Create a new ChatSession
                    chat_session = ChatSession(
                        interview_session_id=interview_session_id
                    )
                    session.add(chat_session)
                    await session.commit()
                    await session.refresh(chat_session)
                    logger.info(
                        f"New chat session {chat_session.id} created for interview session {interview_session_id}")

                return chat_session.id

        except Exception as e:
            logger.error(f"Error creating/retrieving chat session: {e}")
            return None

    @staticmethod
    async def store_interaction(chat_session_id: str, system_question: str, user_answer: str) -> Optional[int]:
        """
        Store a chat interaction in the database.

        Args:
            chat_session_id: ID of the chat session
            system_question: The question from the system
            user_answer: The user's answer

        Returns:
            ID of the created interaction or None if creation failed
        """
        try:
            # Create a new ChatInteraction object with the chat session ID
            new_interaction = ChatInteraction(
                session_id=chat_session_id,
                system_question=system_question,
                user_answer=user_answer
            )

            async for session in get_db():
                # Add the interaction to the database
                session.add(new_interaction)
                await session.commit()
                await session.refresh(new_interaction)
                logger.info(
                    f"Chat interaction {new_interaction.id} successfully stored")
                return new_interaction.id

        except Exception as e:
            logger.error(f"Error storing chat interaction: {e}")
            return None
