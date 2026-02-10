"""
Utility functions for LLM requests and responses.
"""

import json
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def clean_json_response(text: str) -> str:
    """
    Cleans and repairs JSON responses from LLMs.
    Handles common issues like markdown formatting, invalid quotes,
    trailing commas, and extensive model reasoning.
    
    Args:
        text: The LLM response to clean
        
    Returns:
        Clean JSON-compliant string
    """
    original_text = text
    text = text.strip()
    
    # Remove extensive LLM "thinking" processes
    if text.startswith("<think>"):
        think_end = text.find("</think>")
        if think_end != -1:
            text = text[think_end + 8:].strip()
            logger.debug("Removed <think> block from response")
    
    # Remove markdown formatting
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        # Test parse - if successful, no further repairs needed
        json.loads(text)
        return text
    except json.JSONDecodeError:
        # Begin actual repairs
        logger.warning("JSON repair required for malformed response")
        
        # Log truncated original content for debugging
        truncated_original = _truncate_for_log(original_text, max_length=200)
        logger.debug(f"Original content (truncated): {truncated_original}")
        
        # Find first and last brace pair
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first:last+1]
        
        # Apply common JSON fixes
        text = _fix_common_json_errors(text)
        
        try:
            # Test if repair worked
            json.loads(text)
            logger.debug("JSON repair successful")
            return text
        except json.JSONDecodeError:
            # Fallback: extract specific objects
            return _extract_object_from_json(text)
        
def clean_groq_json_response(text: str) -> str:
    """
    Special cleaning for Groq API JSON responses.
    
    Args:
        text: The Groq API response text
        
    Returns:
        Clean JSON string
    """
    # For debugging malformed responses
    logger.debug(f"Cleaning Groq response: {text[:100]}...")
    
    # Groq sometimes adds extra content before/after the JSON
    # Try to extract JSON using regex
    json_match = re.search(r'(\{[\s\S]*\})', text)
    if json_match:
        potential_json = json_match.group(1)
        try:
            # Validate it's parsable
            json.loads(potential_json)
            return potential_json
        except json.JSONDecodeError:
            pass  # Continue with other cleaning methods
    
    # Fix common issues with Groq's JSON output
    cleaned_text = text
    
    # Remove markdown code block markers
    cleaned_text = re.sub(r'```json\s+', '', cleaned_text)
    cleaned_text = re.sub(r'```\s*$', '', cleaned_text)
    
    # Fix unescaped quotes and common JSON errors
    cleaned_text = cleaned_text.replace('\\"', '"')
    cleaned_text = cleaned_text.replace('\\n', '\n')
    
    # Try to parse the cleaned text
    try:
        json.loads(cleaned_text)
        return cleaned_text
    except json.JSONDecodeError:
        # Fall back to regular cleaning if specialized cleaning failed
        logger.warning("Groq-specific cleaning failed, falling back to general JSON cleaning")
        return clean_json_response(text)

def _fix_common_json_errors(text: str) -> str:
    """
    Fixes common JSON errors in LLM outputs.
    
    Args:
        text: The JSON string to repair
        
    Returns:
        Repaired JSON string
    """
    # Remove BOM
    text = text.replace("\ufeff", "")
    
    # Replace single quotes with double quotes for keys and values
    text = re.sub(r"([,{\[]\s*)'(\w+)'\s*:", r'\1"\2":', text)
    text = re.sub(r':\s*\'(.*?)\'(,|})', r': "\1"\2', text)
    
    # Remove trailing commas
    text = re.sub(r',\s*([}\]])', r'\1', text)
    
    # Convert Python booleans to JSON
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b', 'null', text)
    
    return text

def _extract_object_from_json(text: str) -> str:
    """
    Extracts a specific object from malformed JSON.
    Prioritizes "Next" objects commonly found in responses.
    
    Args:
        text: The malformed JSON string
        
    Returns:
        Extracted object as JSON string or fallback JSON
    """
    # Try to extract "Next" object (common in interview responses)
    next_match = re.search(r'"Next"\s*:\s*{([^{}]|{[^{}]*})*}', text)
    if next_match:
        next_content = next_match.group(0)
        try:
            minimal_json = "{" + next_content + "}"
            json.loads(minimal_json)  # Validate
            logger.debug("Successfully extracted 'Next' object")
            return minimal_json
        except json.JSONDecodeError:
            pass
    
    # Try to find any nested object
    pattern = r'"\w+"\s*:\s*{([^{}]|{[^{}]*})*}'
    match = re.search(pattern, text)
    if match:
        obj_content = match.group(0)
        try:
            minimal_json = "{" + obj_content + "}"
            json.loads(minimal_json)
            logger.debug("Extracted nested object")
            return minimal_json
        except json.JSONDecodeError:
            pass
    
    # Fallback for complete failure
    logger.warning("Using fallback JSON due to extraction failure")
    return '{"error":"Failed to extract valid JSON from response"}'

def _truncate_for_log(text: str, max_length: int = 200) -> str:
    """
    Truncates text for logging purposes to avoid overwhelming logs.
    
    Args:
        text: Text to truncate
        max_length: Maximum length for log output
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def prepare_guided_json_schema(response_model: Any) -> Dict[str, Any]:
    """
    Creates a JSON schema from a Pydantic model or schema dictionary.
    
    Args:
        response_model: Pydantic model or schema dictionary
        
    Returns:
        JSON schema as dictionary or None on error
    """
    try:
        if response_model and hasattr(response_model, "model_json_schema"):
            # Pydantic model
            return response_model.model_json_schema()
        elif isinstance(response_model, dict):
            # Already a schema
            return response_model
        else:
            return None
    except Exception as e:
        logger.warning(f"Error creating JSON schema: {e}")
        return None