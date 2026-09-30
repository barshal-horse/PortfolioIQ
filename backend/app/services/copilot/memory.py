"""In-memory session store for Copilot (replaces Qdrant for simplicity)."""

from collections import deque
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid
import threading

from app.services.copilot.state import CopilotState


class InMemorySessionStore:
    """Thread-safe in-memory session store with recent message history."""
    
    def __init__(self, max_messages_per_session: int = 10):
        self._sessions: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._max_messages = max_messages_per_session
    
    def create_session(
        self,
        user_id: str,
        portfolio_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        """Create a new session and return session_id."""
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = {
                "id": session_id,
                "user_id": user_id,
                "portfolio_id": portfolio_id,
                "title": title or f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                "is_active": True,
                "message_count": 0,
                "last_message_at": None,
                "messages": deque(maxlen=self._max_messages),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID."""
        with self._lock:
            return self._sessions.get(session_id)
    
    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """Get all sessions for a user."""
        with self._lock:
            return [
                {k: v for k, v in s.items() if k != "messages"}
                for s in self._sessions.values()
                if s["user_id"] == user_id
            ]
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_name: Optional[str] = None,
        tool_calls: Optional[List] = None,
        tool_results: Optional[List] = None,
        citations: Optional[List] = None,
    ) -> bool:
        """Add a message to session history."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            message = {
                "id": str(uuid.uuid4()),
                "role": role,
                "content": content,
                "agent_name": agent_name,
                "tool_calls": tool_calls or [],
                "tool_results": tool_results or [],
                "citations": citations or [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            session["messages"].append(message)
            session["message_count"] += 1
            session["last_message_at"] = datetime.now(timezone.utc)
            session["updated_at"] = datetime.now(timezone.utc)
            return True
    
    def get_messages(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get recent messages for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            return list(session["messages"])[-limit:]
    
    def update_session(self, session_id: str, **kwargs) -> bool:
        """Update session fields."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            for key, value in kwargs.items():
                if key in session:
                    session[key] = value
            session["updated_at"] = datetime.now(timezone.utc)
            return True
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False


# Global instance
session_store = InMemorySessionStore()


def get_session_store() -> InMemorySessionStore:
    """Get the global session store instance."""
    return session_store