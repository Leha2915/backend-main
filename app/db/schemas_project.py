from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional

class ProjectCreate(BaseModel):
    topic: str
    description: str
    stimuli: List[str]
    n_stimuli: int
    api_key: str
    model: str
    base_url: str
    is_active: bool = True
    n_values_max: int
    min_nodes: int = 0
    voice_enabled: bool = True
    advanced_voice_enabled: bool = True
    interview_mode: int = 1
    tree_enabled: bool = True
    elevenlabs_api_key : str = ""
    max_retries: int = 3
    auto_send: bool = False
    time_limit: int = -1

    r2_account_id: str = None
    r2_access_key_id: str = None
    r2_secret_access_key: str = None
    r2_bucket: str = None

    language: str = "en"

    internal_id: str = ""

    stt_key: str = ""
    stt_endpoint: str = ""

class ProjectOut(BaseModel):
    id: int
    topic: str
    description: str
    stimuli: List[str]
    n_stimuli: int
    slug: str
    created_at: datetime
    is_active: bool
    voice_enabled: bool
    advanced_voice_enabled: Optional[bool] = False
    interview_mode: Optional[int] = 1
    tree_enabled: bool
    auto_send: bool
    time_limit: int
    language: str
    grouped: List[str]

    internal_id: Optional[str] = None

    class Config:
        from_attributes = True
        #orm_mode = True
class ProjectDetailsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    topic: str
    description: str
    stimuli: List[str]
    n_stimuli: int
    model: str
    base_url: str
    created_at: datetime
    is_active: bool
    sessions_total: int
    voice_enabled: bool
    advanced_voice_enabled: Optional[bool] = False
    interview_mode: Optional[int] = 1
    tree_enabled: bool
    last_activity: Optional[datetime] = None
    n_values_max: Optional[int] = None
    min_nodes: Optional[int] = None
    max_retries: int
    auto_send: bool
    time_limit: int
    r2_bucket: Optional[str] = None
    language: str
