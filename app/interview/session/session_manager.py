"""
Session management module for the Interview Engine.
Contains functions for creating, loading, and managing interview sessions.
"""
import uuid
import time
import logging
import os
import warnings
from datetime import datetime
from typing import Dict, Tuple, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models_chat import InterviewSession as InterviewSession
from app.db.models_project import Project
from app.interview.session.interview_session_manager import InterviewSessionManager as InterviewSessionHandler

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages interview sessions and their cache.
    """
    # In-memory cache of active sessions
    _cached_sessions_by_id: Dict[str, Any] = {}

    # 30 min timeout
    _cache_timeout = 1800

    _last_access_times: Dict[str, float] = {}

    @classmethod
    async def setup(cls, project_data: Project, db_session: AsyncSession, session_id: Optional[str] = None) -> Tuple['InterviewSessionHandler', str]:
        """
        Creates a new interview instance or returns an existing one.
        Uses in-memory cache and falls back to the database.

        Args:
            project_data: Project configuration data
            db_session: Database session
            session_id: Optional session ID to load

        Returns:
            Tuple of (InterviewSessionHandler, session_id)
        """
        # Check if local cache should be used (fallback to false if not specified)
        if not os.getenv("USE_LOCAL_CACHE"):
            warnings.warn(
                "'USE_LOCAL_CACHE' not set in .env, fallback to 'false'", UserWarning)

        enable_cache = os.getenv(
            "USE_LOCAL_CACHE", "false").lower() in ("1", "true", "yes")

        # Generate new session_id if none provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Created new session: {session_id}")

        # Try to get from cache if enabled
        if enable_cache and session_id in cls._cached_sessions_by_id:
            cls._last_access_times[session_id] = time.time()
            logger.info(f"Found cached session: {session_id}")
            interview_session = cls._cached_sessions_by_id[session_id]
            cls._cleanup_cache()
            return interview_session, session_id

        # Try to find resumable session in database
        try:
            await db_session.rollback()

            stmt = select(InterviewSession).where(
                InterviewSession.id == session_id)
            result = await db_session.execute(stmt)
            db_interview_session = result.scalar_one_or_none()

            if db_interview_session:
                # Load interview handler from database
                if db_interview_session.chat_data:
                    interview_session = InterviewSessionHandler.from_dict(
                        db_interview_session.chat_data)
                else:
                    interview_session = InterviewSessionHandler(
                        project_data, session_id)
                    await interview_session.init_chats()

                if enable_cache:
                    cls._cached_sessions_by_id[session_id] = interview_session
                    cls._last_access_times[session_id] = time.time()
                    cls._cleanup_cache()

                return interview_session, session_id

        except Exception as e:
            logger.error(f"Error accessing database: {e}", exc_info=True)
            await db_session.rollback()

        # If not found anywhere, create new handler
        logger.info("No session exists. Creating new session...")
        interview_session = InterviewSessionHandler(project_data, session_id)
        await interview_session.init_chats()

        try:
            new_json = interview_session.to_dict()
            new_db_session = InterviewSession(
                project_id=project_data.id,
                id=session_id,
                chat_data=new_json,
                created_at=datetime.now()
            )

            db_session.add(new_db_session)
            await db_session.commit()

            logger.info(
                f"New database session created: {session_id} (Interview + Chat)")
        except Exception as e:
            logger.error(
                f"Error creating database session: {e}", exc_info=True)
            await db_session.rollback()

        if enable_cache:
            cls._cached_sessions_by_id[session_id] = interview_session
            cls._last_access_times[session_id] = time.time()
            cls._cleanup_cache()

        return interview_session, session_id

    @classmethod
    def _cleanup_cache(cls):
        """Cleans up expired entries from the cache"""
        current_time = time.time()
        sessions_to_remove = []

        # Find expired sessions
        for session_id, last_access in cls._last_access_times.items():
            if current_time - last_access > cls._cache_timeout:
                sessions_to_remove.append(session_id)

        # Remove expired sessions
        for session_id in sessions_to_remove:
            if session_id in cls._cached_sessions_by_id:
                del cls._cached_sessions_by_id[session_id]
            if session_id in cls._last_access_times:
                del cls._last_access_times[session_id]

            logger.info(
                f"Removed session {session_id} from cache due to timeout")

    # TODO: Not currently used, but could be useful - complete CRUD interface
    @classmethod
    async def remove_session(cls, session_id: str, db_session: Optional[AsyncSession] = None):
        """
        Removes a session from cache and optionally from the database.

        Args:
            session_id: The session ID to remove
            db_session: Optional database session for database removal

        Returns:
            True if successfully removed from database, False otherwise
        """
        if session_id in cls._cached_sessions_by_id:
            del cls._cached_sessions_by_id[session_id]
            logger.info(f"Session {session_id} removed from cache")
        if session_id in cls._last_access_times:
            del cls._last_access_times[session_id]

        # Remove from database if requested
        if db_session:
            try:
                stmt = select(InterviewSession).where(
                    InterviewSession.id == session_id)
                result = await db_session.execute(stmt)
                interview = result.scalar_one_or_none()

                if interview:
                    await db_session.delete(interview)
                    await db_session.commit()
                    logger.info(f"Session {session_id} removed from database")
                    return True
            except Exception as e:
                logger.error(f"Unable to delete session: {e}", exc_info=True)
                await db_session.rollback()

        return False
