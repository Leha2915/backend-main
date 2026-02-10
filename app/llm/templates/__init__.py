"""
Templates package for LLM prompts.
Contains specialized templates for element analysis and question generation.
"""

from .element_analysis_templates import ELEMENT_ANALYSIS_TEMPLATES
from .question_generation_templates import QUESTION_GENERATION_TEMPLATES

# Combine templates for backwards compatibility if needed
ALL_TEMPLATES = {
    **ELEMENT_ANALYSIS_TEMPLATES,
    **QUESTION_GENERATION_TEMPLATES
}