"""
Standardized handling of structured output formats for different LLM providers.
Supports JSON Schema, JSON Object, and guided JSON formats consistently across
all supported providers.
"""

import logging
import re
from enum import Enum
from typing import Dict, Any, Optional, Union, Literal

from fastapi import params

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Output format types supported by various LLM providers"""
    TEXT = "text"                   # Plain text output
    JSON_OBJECT = "json_object"     # Generic JSON object
    JSON_SCHEMA = "json_schema"     # Structured output with schema validation


class StructuredOutputManager:

    GROQ_STRUCTURED_OUTPUT_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct"
    
    ]
    """
    Manages structured output requests across different LLM providers.
    Ensures consistent parameter formatting for JSON responses.
    """

    # List of OpenAI models that support full structured output
    OPENAI_STRUCTURED_OUTPUT_MODELS = [
        "gpt-4o", 
        "gpt-4o-mini",
        "gpt-4-turbo"  # Newer versions support it
    ]

    @staticmethod
    def prepare_parameters(
        provider: str,
        output_format: OutputFormat = OutputFormat.TEXT,
        schema: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Prepares parameters for structured output based on the provider.
        """
        params = kwargs.copy()
    
        # Remove any existing conflicting parameters
        for key in ["response_format", "guided_json", "extra_body"]:
            if key in params:
                params.pop(key)
                logger.info(f"Removed existing '{key}' parameter to avoid conflicts")
    
        # Process based on provider and format
        if provider == "groq":
            params = StructuredOutputManager._prepare_groq_parameters(
                output_format, schema, model, params)
        elif provider == "openai":
            params = StructuredOutputManager._prepare_openai_parameters(
                output_format, schema, model, params)
        elif provider == "anthropic":
            params = StructuredOutputManager._prepare_anthropic_parameters(
                output_format, schema, params)
        elif provider in ["vllm", "academic_cloud"]:
            # Both vLLM and Academic Cloud use the same parameter format
            params = StructuredOutputManager._prepare_vllm_parameters(
                output_format, schema, params)
        else:
            # For unknown providers, use a conservative approach
            logger.warning(f"Unknown provider: {provider}, using conservative parameter approach")
            params = StructuredOutputManager._prepare_unknown_provider_parameters(
                output_format, schema, params)
    
        return params

    @staticmethod
    def _prepare_groq_parameters(
        output_format: OutputFormat,
        schema: Optional[Dict[str, Any]],
        model: Optional[str] = None,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Prepares parameters specifically for Groq's API.
        """
        params = params or {}
        model_str = str(model or "").lower()
        
        # Check if model supports structured output with json_schema
        supports_json_schema = any(
            supported_model.lower() in model_str 
            for supported_model in StructuredOutputManager.GROQ_STRUCTURED_OUTPUT_MODELS
        )
        
        if output_format == OutputFormat.JSON_SCHEMA and schema:
            if supports_json_schema:
                # Correct format for Groq JSON schema
                params["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": schema
                    }
                }
                logger.debug(f"Using full json_schema format for supported Groq model: {model}")
            else:
                # Fall back to json_object mode for unsupported models
                params["response_format"] = {"type": "json_object"}
                logger.debug(f"Using json_object mode for Groq model {model} (schema validation not supported)")
                
                # Flag that we may need to add JSON instructions
                params["_requires_json_instruction"] = True
        
        elif output_format == OutputFormat.JSON_OBJECT:
            # Simple JSON object format - all Groq models support this
            params["response_format"] = {"type": "json_object"}
            logger.debug("Using json_object mode for Groq")
            
            # Flag that we may need to add JSON instructions
            params["_requires_json_instruction"] = True
            
        elif output_format == OutputFormat.TEXT:
            # Plain text format
            params["response_format"] = {"type": "text"}
            logger.debug("Using text format for Groq")
            
        return params

    @staticmethod
    def _prepare_openai_parameters(
        output_format: OutputFormat,
        schema: Optional[Dict[str, Any]],
        model: Optional[str] = None,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Prepares parameters specifically for OpenAI.
        
        Handles both newer models with structured output support and older models
        that only support JSON mode.
        
        Args:
            output_format: Desired output format
            schema: JSON schema for structured responses
            model: OpenAI model name (required for determining capabilities)
            params: Base parameters dictionary
            
        Returns:
            Updated parameters dictionary with proper format settings
        """
        params = params or {}
        model_str = str(model or "").lower()
        
        # Check if model supports structured output
        supports_structured_output = False
        if model_str:
            supports_structured_output = any(
                model_prefix in model_str 
                for model_prefix in StructuredOutputManager.OPENAI_STRUCTURED_OUTPUT_MODELS
            )
            
            # Also check for date-versioned models like gpt-4o-2024-08-06
            if not supports_structured_output and re.search(r'gpt-4o-\d{4}-\d{2}-\d{2}', model_str):
                supports_structured_output = True
        
        # Configure based on output format, schema availability and model capabilities
        if output_format == OutputFormat.JSON_SCHEMA and schema:
            if supports_structured_output:
                # Use native structured output format for newer models (GPT-4o+)
                params["response_format"] = {
                    "type": "json_schema",
                    "schema": schema
                }
                logger.info(f"Using native structured output with JSON schema for {model}")
            else:
                # Fall back to JSON mode for older models, but validate schema client-side
                params["response_format"] = {"type": "json_object"}
                
                # Ensure we have a JSON instruction in the messages
                # This is required by OpenAI when using JSON mode
                params["_requires_json_instruction"] = True
                logger.info(f"Using JSON mode for {model} (schema validation will be client-side)")
                
        elif output_format == OutputFormat.JSON_OBJECT:
            # Simple JSON object format - all OpenAI models support this
            params["response_format"] = {"type": "json_object"}
            
            # Ensure we have a JSON instruction in the messages
            params["_requires_json_instruction"] = True
            logger.info("Using JSON object mode for OpenAI")
            
        # For TEXT format, OpenAI doesn't need special parameters
            
        return params

    @staticmethod
    def _prepare_anthropic_parameters(
        output_format: OutputFormat,
        schema: Optional[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepares parameters specifically for Anthropic's Claude models.
        
        Anthropic supports basic JSON object output but not schema validation.
        We use a combination of response_format parameter and prompt instructions.
        
        Args:
            output_format: Desired output format
            schema: JSON schema (will be used for prompt instructions only)
            params: Base parameters dictionary
            
        Returns:
            Updated parameters dictionary with Anthropic-compatible settings
        """
        # For Anthropic's API format
        if output_format in [OutputFormat.JSON_SCHEMA, OutputFormat.JSON_OBJECT]:
            # Set standard JSON output format
            params["response_format"] = {"type": "json_object"}
            
            # Flag that we need JSON instructions in the prompt
            params["_requires_json_instruction"] = True
            
            if output_format == OutputFormat.JSON_SCHEMA and schema:
                # Special flag for client.py to handle schema in prompt
                # This will be removed before API call
                params["_schema_for_prompt"] = schema
                logger.info("Added schema for prompt instructions (Anthropic doesn't support schema validation)")
                
            logger.info("Using response_format.json_object for Anthropic")
            
        return params
    
    @staticmethod
    def _prepare_unknown_provider_parameters(
        output_format: OutputFormat,
        schema: Optional[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Conservative parameter preparation for unknown providers.
        
        For providers we don't recognize, we take a minimal approach and rely
        on prompt instructions rather than special parameters.
        
        Args:
            output_format: Desired output format
            schema: JSON schema (will be used for prompt instructions only)
            params: Base parameters dictionary
            
        Returns:
            Updated parameters with minimal modifications
        """
        # For unknown providers, don't add special parameters that might cause errors
        # Instead, rely on prompt instructions for structured output
        
        if output_format in [OutputFormat.JSON_SCHEMA, OutputFormat.JSON_OBJECT]:
            # Flag that we need JSON instructions in the prompt
            params["_requires_json_instruction"] = True
            
            if output_format == OutputFormat.JSON_SCHEMA and schema:
                # Store schema for potential prompt enhancement
                params["_schema_for_prompt"] = schema

            logger.info("Using prompt instructions only for unknown provider (no special parameters)")

        return params

    @staticmethod
    def _prepare_vllm_parameters(
        output_format: OutputFormat,
        schema: Optional[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepares parameters specifically for vLLM/Academic Cloud.
        
        Both vLLM and Academic Cloud instances (like chat-ai.academiccloud.de) 
        use the same underlying technology and parameter format.
        
        Args:
            output_format: Desired output format
            schema: JSON schema for structured output
            params: Base parameters dictionary
            
        Returns:
            Updated parameters dictionary
        """
        # vLLM/Academic Cloud uses extra_body.guided_json for structured output
        if (output_format == OutputFormat.JSON_SCHEMA or output_format == OutputFormat.JSON_OBJECT) and schema:
            # Pass the complete schema directly in extra_body.guided_json
            # This is the official recommended way for vLLM/Academic Cloud
            params["extra_body"] = {"guided_json": schema}
            logger.info("Added extra_body.guided_json for vLLM/Academic Cloud")
        elif output_format == OutputFormat.JSON_OBJECT and not schema:
            # Simple guidance for JSON output when no schema is provided
            params["extra_body"] = {"guided_json": {"type": "object"}}
            logger.info("Added basic JSON structure guidance for vLLM/Academic Cloud")

        # Note: TEXT format doesn't need special handling for vLLM
            
        return params

    @staticmethod
    def ensure_json_instruction_in_messages(messages: list) -> list:
        """
        Ensures that messages contain an instruction to output JSON.
        This is required by OpenAI when using JSON mode.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Updated messages list with JSON instruction if needed
        """
        # Check if any message already contains a JSON instruction
        has_json_instruction = any(
            "json" in str(msg.get("content", "")).lower() 
            for msg in messages
        )
        
        if not has_json_instruction:
            # Try to add to system message if one exists
            for msg in messages:
                if msg.get("role") == "system":
                    msg["content"] = f"{msg['content']} Please respond with a valid JSON object."
                    logger.info("Added JSON instruction to existing system message")
                    return messages
            
            # If no system message exists, add one
            messages.insert(0, {
                "role": "system",
                "content": "Please respond with a valid JSON object."
            })
            logger.info("Added new system message with JSON instruction")
            
        return messages
    
    @staticmethod
    def ensure_json_instruction_for_groq(messages: list) -> list:
        """
        Ensures that messages contain an instruction to output JSON for Groq.
        This is required when using JSON object mode.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Updated messages list with JSON instruction if needed
        """
        # Check if any message already contains a JSON instruction
        has_json_instruction = any(
            "json" in str(msg.get("content", "")).lower() 
            for msg in messages
        )
        
        if not has_json_instruction:
            # Try to add to system message if one exists
            for msg in messages:
                if msg.get("role") == "system":
                    msg["content"] = f"{msg['content']} Please respond with a valid JSON object."
                    logger.info("Added JSON instruction to existing system message for Groq")
                    return messages
            
            # If no system message exists, add one
            messages.insert(0, {
                "role": "system",
                "content": "Please respond with a valid JSON object."
            })
            logger.info("Added new system message with JSON instruction for Groq")
            
        return messages

    @staticmethod
    def convert_schema_for_provider(
        schema: Dict[str, Any],
        provider: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Converts a JSON schema to be compatible with a specific provider.
        Some providers might have special requirements or limitations.

        Args:
            schema: The JSON schema to convert
            provider: Target provider name
            model: Model name for provider-specific adjustments

        Returns:
            Provider-compatible JSON schema
        """
        if provider == "openai":
            # OpenAI has specific schema requirements for structured output
            model_str = str(model or "").lower()
            supports_structured_output = any(
                model_prefix in model_str 
                for model_prefix in StructuredOutputManager.OPENAI_STRUCTURED_OUTPUT_MODELS
            ) or re.search(r'gpt-4o-\d{4}-\d{2}-\d{2}', model_str)
            
            if supports_structured_output:
                # Newer models might have specific schema requirements
                # Currently no adjustments needed, but placeholder for future changes
                pass
                
        return schema
    
    @staticmethod
    def enhance_prompt_with_schema(messages: list, schema: Dict[str, Any]) -> list:
        """
        Enhances prompt messages with schema information for providers 
        that don't support schema validation directly.
        
        Args:
            messages: List of message dictionaries
            schema: JSON schema to include in instructions
            
        Returns:
            Updated messages list with schema instructions
        """
        # Format the schema for human readability
        import json
        schema_str = json.dumps(schema, indent=2)
        
        schema_instruction = (
            "Please format your response as JSON that matches this schema:\n"
            f"```json\n{schema_str}\n```\n"
            "Ensure your response is valid JSON and follows this schema exactly."
        )
        
        # Try to add to system message if one exists
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = f"{msg['content']}\n\n{schema_instruction}"
                logger.debug("Added schema instructions to existing system message")
                return messages
        
        # If no system message exists, add one
        messages.insert(0, {
            "role": "system",
            "content": schema_instruction
        })
        logger.debug("Added new system message with schema instructions")
        
        return messages
