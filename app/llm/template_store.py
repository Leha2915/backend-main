"""
Prompt templates for LLM interactions.
Provides a centralized store for all prompt templates.
"""

from typing import Dict, Any

from app.llm.templates import ALL_TEMPLATES
from app.llm.templates.element_analysis_templates import ELEMENT_ANALYSIS_TEMPLATES
from app.llm.templates.question_generation_templates import QUESTION_GENERATION_TEMPLATES

# Maintain backwards compatibility
TEMPLATES = ALL_TEMPLATES

def render_template(name: str, **vars: Any) -> str:
    """
    Format a template with provided variables or provide a helpful error message.
    
    Args:
        name: The name of the template to render
        **vars: Variables to insert into the template
        
    Returns:
        The formatted template string
        
    Raises:
        KeyError: If the template name doesn't exist
        ValueError: If a required template variable is missing
    """
    if name not in TEMPLATES:
        raise KeyError(f"Unknown template '{name}'.")
    try:
        return TEMPLATES[name].format(**vars)
    except KeyError as miss:
        raise ValueError(f"Missing template variable {miss}") from None
