# app/models.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AssistantNext(BaseModel):
    NextQuestion: str = Field(...,
                              description="Follow-up question for the interviewee")
    AskingIntervieweeFor: str = Field(...,
                                      description="Chain ID or cue (e.g. C1.1)")
    ThoughtProcess: str = Field(
        ..., description="Short explanation of why this question was chosen")
    EndOfInterview: bool = Field(
        False,
        description="Set to True when the laddering interview is finished",
    )
    session_id: Optional[str] = None
    
    CompletionReason: Optional[str] = Field(
        None,
        description="Reason why the interview ended (VALUES_LIMIT_REACHED, INTERVIEW_COMPLETE, etc.)",
    )
    ValuesCount: Optional[int] = Field(
        None,
        description="Current number of values identified in the interview"
    )
    ValuesMax: Optional[int] = Field(
        None,
        description="Maximum number of values allowed for this interview"
    )
    ValuesReached: Optional[bool] = Field(
        None,
        description="Whether the values limit has been reached"
    )


class AssistantChain(BaseModel):
    Attribute: str
    Consequence: List[str]
    Values: List[str]


class AssistantResponse(BaseModel):
    Next: AssistantNext
    Chains: List[AssistantChain]
    Tree: Optional[Dict[str, Any]] = None  # Add tree structure

class History(BaseModel):
    content: List[List[Dict[str, str]]]