"""
Centralized LLM client for consistent API access across different providers.
Supports structured outputs with provider-specific optimizations.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from app.llm.utils import clean_json_response, clean_groq_json_response
from app.llm.structured_output_manager import StructuredOutputManager, OutputFormat

logger = logging.getLogger(__name__)

class LlmClient:
    """
    Centralized client for all LLM API requests.
    Supports various LLM providers with optimized parameters and structured output handling.
    """
    
    # Provider-specific token limits
    TOKEN_LIMITS = {
        "default": 1024,
        "openai": 4096,
        "groq": 32768,  # (effectively unlimited for most use cases)
        "academic_cloud": 1500,  
        "vllm": 1500,
        "anthropic": 4096
    }
    
    # Default temperature values by provider
    TEMPERATURE_DEFAULTS = {
        "default": 0.3,
        "openai": 0.5,
        "groq": 0.4,
        "academic_cloud": 0.5,  
        "vllm": 0.5,
        "anthropic": 0.5
    }
    
    # Singleton instance
    _instance = None
    _default_client = None
    _default_model = None
    
    def __init__(self, client: Any, model: str = None):
        """
        Initialize an LLM client.
        
        Args:
            client: OpenAI-compatible client (OpenAI, Anthropic, etc.)
            model: Default model name for requests
        """
        self.client = client
        self.model = model
        self.base_url = getattr(client, "base_url", "") or ""
        
        # Determine provider-specific properties based on URL
        self.provider = self._detect_provider(self.base_url)
        logger.info(f"Initialized LlmClient with provider: {self.provider}")
    
    @classmethod
    def get_default_client(cls) -> Optional['LlmClient']:
        """
        Returns the default client used in the application.
        """
        if not cls._default_client:
            return None
        
        # Ensure _instance exists if _default_client is available
        if not cls._instance and cls._default_client:
            cls._instance = cls(cls._default_client, cls._default_model)
                
        return cls._instance
    
    @classmethod
    def set_default_client(cls, client: Any, model: str) -> 'LlmClient':
        """
        Sets the default client for the application.
        """
        cls._default_client = client
        cls._default_model = model
        cls._instance = cls(client, model)
        return cls._instance
    
    def _detect_provider(self, base_url: str) -> str:
        """
        Detects the LLM provider based on the base_url.
        
        Args:
            base_url: The provider URL
            
        Returns:
            Provider name as string
        """
        url_str = str(base_url).lower() if base_url else ""
        host = (urlparse(url_str).hostname or "").lower()
        
        if "openai.com" in host:
            return "openai"
        elif "anthropic.com" in host:
            return "anthropic"
        elif "groq.com" in host:
            return "groq"
        elif "chat-ai.academiccloud.de" in url_str or "vllm" in url_str:
            # Treat academic_cloud and vllm as the same provider
            return "academic_cloud"
        else:
            return "unknown"
    
    def _prepare_messages_for_provider(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Prepares messages for the specific provider.
        
        Args:
            messages: List of messages in OpenAI format
            
        Returns:
            Adjusted message list
        """
        if not messages:
            return []
            
        # Copy messages to avoid modifying originals
        prepared_messages = messages.copy()
        
        if self.provider == "anthropic":
            # Anthropic requires a closing user message
            if prepared_messages[-1]["role"] != "user":
                prepared_messages.append({"role": "user", "content": "answer"})
                
        elif self.provider == "groq":
            # Groq only accepts 'role' and 'content'
            sanitized = []
            for m in prepared_messages:
                role = m.get("role")
                content = m.get("content", "")
                if not isinstance(content, str):
                    try:
                        content = json.dumps(content, ensure_ascii=False)
                    except Exception:
                        content = str(content)
                if role:
                    sanitized.append({"role": role, "content": content})
            prepared_messages = sanitized
            
        return prepared_messages
    
    def get_optimal_token_limit(self, model: str = None) -> int:
        """
        Returns the optimal token limit based on model and provider.
        
        Args:
            model: Optional model name override
            
        Returns:
            Recommended token limit for the response
        """
        # Get provider-specific token limit with fallback to default
        return self.TOKEN_LIMITS.get(self.provider, self.TOKEN_LIMITS["default"])
    
    def get_default_temperature(self) -> float:
        """
        Returns the default temperature value for the current provider.
        
        Returns:
            Default temperature value (0.0-1.0)
        """
        return self.TEMPERATURE_DEFAULTS.get(self.provider, self.TEMPERATURE_DEFAULTS["default"])
        
    async def query_with_structured_output(self,
                                         messages: List[Dict[str, str]],
                                         schema: Dict[str, Any],
                                         model: str = None,
                                         temperature: Optional[float] = None,
                                         **kwargs) -> str:
        """
        Executes an LLM request with standardized structured output handling.
        
        This is the primary method for making LLM requests that expect structured 
        JSON responses. It applies provider-specific optimizations for the best results.
        
        Args:
            messages: Messages for the LLM request
            schema: JSON schema for the expected response structure
            model: Model name (overrides default model)
            temperature: Temperature parameter (creativity, provider-specific defaults if None)
            **kwargs: Additional parameters for the API call
            
        Returns:
            The raw response from the LLM
            
        Raises:
            ValueError: If client or model is missing
            Exception: If all request attempts fail
        """
        # Check if client and model are available
        if not self.client:
            raise ValueError("No LLM client available. Please specify client in constructor.")
            
        # Prepare parameters
        model = model or self.model or self._default_model
        if not model:
            raise ValueError("No model specified. Please pass model parameter or specify in constructor.")
        
        # Only set temperature if explicitly provided, otherwise use provider defaults
        base_params = {"messages": self._prepare_messages_for_provider(messages)}
        if temperature is not None:
            base_params["temperature"] = temperature
        else:
            base_params["temperature"] = self.get_default_temperature()
            
        # Add optimal token limit if not provided
        if "max_tokens" not in kwargs and "max_tokens" not in base_params:
            base_params["max_tokens"] = self.get_optimal_token_limit(model)
        
        # Add additional parameters
        for key, value in kwargs.items():
            base_params[key] = value
        
        # Apply structured output parameters based on provider
        request_params = StructuredOutputManager.prepare_parameters(
            provider=self.provider,
            output_format=OutputFormat.JSON_SCHEMA,
            schema=schema,
            model=model,
            **base_params
        )
        
        # For providers that require JSON instructions in prompt
        if "_requires_json_instruction" in request_params:
            request_params.pop("_requires_json_instruction")
            request_params["messages"] = StructuredOutputManager.ensure_json_instruction_in_messages(
                request_params["messages"]
            )

        # For providers that need schema in prompt (not in API params)
        if "_schema_for_prompt" in request_params:
            schema_for_prompt = request_params.pop("_schema_for_prompt")  # Remove from params
            request_params["messages"] = StructuredOutputManager.enhance_prompt_with_schema(
                request_params["messages"], schema_for_prompt
            )
            
        # Add model back into request_params for the API call if not present
        if "model" not in request_params:
            request_params["model"] = model
            
        logger.info(f"Making structured output request to {self.provider} with {model}")
        
        try:
            # Make primary API call with fully structured parameters
            response = await self.client.chat.completions.create(**request_params)
            content = response.choices[0].message.content.strip()
            logger.info(f"Structured output request successful")
            return content
        except Exception as e:
            logger.error(f"Structured output request failed: {e}")
            
            # Try fallback with simple JSON object format
            try:
                logger.warning("Trying fallback with simple JSON object format")
                fallback_params = StructuredOutputManager.prepare_parameters(
                    provider=self.provider,
                    output_format=OutputFormat.JSON_OBJECT,
                    model=model,
                    **{k: v for k, v in base_params.items() if k != "model"}
                )
                
                # Add model back into fallback_params
                if "model" not in fallback_params:
                    fallback_params["model"] = model
                    
                # Add JSON instruction if needed
                if "_requires_json_instruction" in fallback_params:
                    fallback_params.pop("_requires_json_instruction")
                    fallback_params["messages"] = StructuredOutputManager.ensure_json_instruction_in_messages(
                        fallback_params["messages"]
                    )
                    
                response = await self.client.chat.completions.create(**fallback_params)
                content = response.choices[0].message.content.strip()
                logger.info("Fallback to JSON object format successful")
                return content
            except Exception as fallback_error:
                logger.error(f"JSON object fallback failed: {fallback_error}")
                
                # Last resort: minimal request with no format specification
                try:
                    logger.warning("Trying minimal request as final fallback")
                    minimal_params = {
                        "model": model,
                        "messages": self._prepare_messages_for_provider(messages)
                    }
                    response = await self.client.chat.completions.create(**minimal_params)
                    content = response.choices[0].message.content.strip()
                    logger.info("Minimal request successful")
                    return content
                except Exception as minimal_error:
                    logger.error(f"All fallbacks failed: {minimal_error}")
                    raise e  # Re-raise original error
