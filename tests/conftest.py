import pytest
import requests
from typing import Dict, List, Any

# ======================================================================
#  1. CONFIGURATION FOR "INTERVIEW WORKFLOW" TESTS
# ======================================================================

INTERVIEW_CONFIG = {
    "api_url": "http://localhost:8000/interview/chat",
    "openai_api_key": "your-openai-api-key-here",  # Replace with your LLM provider API key
    "model": "gpt-4",                              # Replace with your preferred model
    "base_url": "https://api.openai.com/v1",       # Change to your provider's base URL
    "admin_key": "admin-test-key",                 # Key for admin operations (can be any value for tests)
    "elevenlabs_api_key": "your-elevenlabs-key",   # Optional: Replace if using voice features
    "max_retries": 3                               # Adjust based on your needs
}
INTERVIEW_TOPIC = "Personalizing a Music Streaming App"
INTERVIEW_STIMULUS = "Offline playback – listen without internet"

# ======================================================================
#  2. CONFIGURATION FOR "SMART HOME" TESTS
# ======================================================================

SMART_HOME_CONFIG = {
    "api_url": "http://localhost:8000/interview/chat",
    "openai_api_key": "your-openai-api-key-here",  # Replace with your LLM provider API key
    "model": "gpt-4",                              # Replace with your preferred model
    "base_url": "https://api.openai.com/v1",       # Change to your provider's base URL
    "admin_key": "admin-test-key",                 # Key for admin operations (can be any value for tests)
    "elevenlabs_api_key": "your-elevenlabs-key",   # Optional: Replace if using voice features
    "max_retries": 3                               # Adjust based on your needs
}
SMART_HOME_TOPIC = "Smart Home Technology"
SMART_HOME_STIMULI = ["Voice-controlled assistants", "Home security systems"]

# ======================================================================
#  3. PROJECT CREATION FIXTURES (for both scenarios)
# ======================================================================

@pytest.fixture(scope="module")
def created_interview_project_slug():
    """Creates the interview test project and returns its slug."""
    try:
        print("\nCreating/checking interview test project...")
        project_data = {
            "topic": INTERVIEW_TOPIC,
            "description": "Test project for interview workflow",
            "stimuli": [INTERVIEW_STIMULUS],
            "n_stimuli": 1,
            "api_key": INTERVIEW_CONFIG["openai_api_key"],
            "base_url": INTERVIEW_CONFIG["base_url"],
            "model": INTERVIEW_CONFIG["model"],
            "n_values_max": -1,  # Values limit for test project
            "elevenlabs_api_key": INTERVIEW_CONFIG["elevenlabs_api_key"],  
            "max_retries": INTERVIEW_CONFIG["max_retries"],
            "voice_enabled": False,
            "advanced_voice_enabled": False,
            "tree_enabled": True
        }
        resp = requests.post("http://localhost:8000/test-project", json=project_data)
        
        # ENHANCED: Better error handling
        if not resp.ok:
            print(f"❌ HTTP {resp.status_code}: {resp.text}")
            try:
                error_detail = resp.json()
                print(f"Error details: {error_detail}")
            except:
                pass
        
        resp.raise_for_status()
        generated_slug = resp.json().get("slug")
        print(f"✅ Interview test project created: {generated_slug}")
        return generated_slug
    except Exception as e:
        pytest.fail(f"⚠️ Error creating interview project: {e}")

@pytest.fixture(scope="module")
def created_smart_home_project_slug():
    """Creates the smart home test project and returns its slug."""
    try:
        print("\nCreating/checking smart home test project...")
        project_data = {
            "topic": SMART_HOME_TOPIC,
            "description": "Test project for smart home testing",
            "stimuli": SMART_HOME_STIMULI,
            "n_stimuli": len(SMART_HOME_STIMULI),
            "api_key": SMART_HOME_CONFIG["openai_api_key"],
            "base_url": SMART_HOME_CONFIG["base_url"],
            "model": SMART_HOME_CONFIG["model"],
            "n_values_max": -1,  # Values limit for smart home tests
            "elevenlabs_api_key": SMART_HOME_CONFIG["elevenlabs_api_key"],  # Added required field
            "max_retries": SMART_HOME_CONFIG["max_retries"],  # Added required field
            "voice_enabled": False,  # Added optional fields
            "advanced_voice_enabled": False,
            "tree_enabled": True
        }
        resp = requests.post("http://localhost:8000/test-project", json=project_data)
        
        # ENHANCED: Better error handling
        if not resp.ok:
            print(f"❌ HTTP {resp.status_code}: {resp.text}")
            try:
                error_detail = resp.json()
                print(f"Error details: {error_detail}")
            except:
                pass
        
        resp.raise_for_status()
        generated_slug = resp.json().get("slug")
        print(f"✅ Smart home test project created: {generated_slug}")
        return generated_slug
    except Exception as e:
        pytest.fail(f"⚠️ Error creating smart home project: {e}")

# ======================================================================
#  4. TEST CLIENTS AND THEIR FIXTURES
# ======================================================================

# --- Client for Interview Workflow ---
class TestInterviewClient:
    """Test client for interview workflow testing."""
    
    def __init__(self, project_slug: str, topic: str = INTERVIEW_TOPIC, stimulus: str = INTERVIEW_STIMULUS):
        self.session_id = None
        self.topic = topic
        self.stimulus = stimulus
        self.messages = []
        self.project_slug = project_slug

    def send_message(self, message_content: str, print_response: bool = True) -> Dict[str, Any]:
        """
        Sends a message to the interview API and returns the response.
        
        Args:
            message_content: The content of the message to send
            print_response: Whether to print the response (default: True)
            
        Returns:
            The API response data
        """
        self.messages.append({"role": "user", "content": message_content})
        payload = {
            "template_name": "queue_laddering",
            "template_vars": {"topic": self.topic, "stimulus": self.stimulus},
            "message": message_content,
            "session_id": self.session_id,
            "projectSlug": self.project_slug,
            "stimulus": self.stimulus
        }
        try:
            print(f"\nREQUEST | Session-ID: {self.session_id} | Project: {self.project_slug}")
            resp = requests.post(INTERVIEW_CONFIG["api_url"], json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            
            if "Next" in data and "session_id" in data["Next"]:
                self.session_id = data["Next"]["session_id"]
            elif "session_id" in data:
                self.session_id = data["session_id"]

            self.messages.append({"role": "assistant", "content": data["Next"]["NextQuestion"]})
            
            # Debug output for values information
            if "Next" in data:
                values_count = data["Next"].get("ValuesCount")
                values_max = data["Next"].get("ValuesMax")
                values_reached = data["Next"].get("ValuesReached")
                completion_reason = data["Next"].get("CompletionReason")
                
                if any([values_count is not None, values_max is not None, values_reached, completion_reason]):
                    print(f"VALUES INFO: Count={values_count}, Max={values_max}, Reached={values_reached}, Reason={completion_reason}")
            
            return data
        except Exception as e:
            print(f"❌ Error: {e}")
            raise

    def reset(self):
        """Reset the client state."""
        self.session_id = None
        self.messages = []

@pytest.fixture
def interview_client(created_interview_project_slug: str):
    """Fixture providing an interview test client."""
    client = TestInterviewClient(project_slug=created_interview_project_slug)
    yield client
    client.reset()

# --- Client for Smart Home ---
class SmartHomeTestClient:
    """Test client for smart home testing."""
    
    def __init__(self, project_slug: str, topic: str = SMART_HOME_TOPIC, stimulus: str = SMART_HOME_STIMULI[0]):
        self.session_id = None
        self.topic = topic
        self.stimulus = stimulus
        self.messages = []
        self.project_slug = project_slug

    def send_message(self, message_content: str, print_response: bool = True) -> Dict[str, Any]:
        """
        Sends a message to the smart home API and returns the response.
        
        Args:
            message_content: The content of the message to send
            print_response: Whether to print the response (default: True)
            
        Returns:
            The API response data
        """
        self.messages.append({"role": "user", "content": message_content})
        payload = {
            "template_name": "queue_laddering",
            "template_vars": {"topic": self.topic, "stimulus": self.stimulus},
            "message": message_content,
            "session_id": self.session_id,
            "projectSlug": self.project_slug,
            "stimulus": self.stimulus
        }
        try:
            print(f"\nREQUEST | Session-ID: {self.session_id} | Project: {self.project_slug}")
            resp = requests.post(SMART_HOME_CONFIG["api_url"], json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            
            if "Next" in data and "session_id" in data["Next"]:
                self.session_id = data["Next"]["session_id"]
            elif "session_id" in data:
                self.session_id = data["session_id"]

            self.messages.append({"role": "assistant", "content": data["Next"]["NextQuestion"]})
            
            # Debug output for values information
            if "Next" in data:
                values_count = data["Next"].get("ValuesCount")
                values_max = data["Next"].get("ValuesMax")
                values_reached = data["Next"].get("ValuesReached")
                completion_reason = data["Next"].get("CompletionReason")
                end_of_interview = data["Next"].get("EndOfInterview")
                
                if any([values_count is not None, values_max is not None, values_reached, completion_reason]):
                    print(f"VALUES INFO: Count={values_count}, Max={values_max}, Reached={values_reached}")
                    print(f"END INFO: EndOfInterview={end_of_interview}, Reason={completion_reason}")
            
            return data
        except Exception as e:
            print(f"❌ Error: {e}")
            raise

    def change_stimulus(self, new_stimulus: str):
        """Change the current stimulus."""
        self.stimulus = new_stimulus
        print(f"\nChanged stimulus to: {new_stimulus}")

    def reset(self):
        """Reset the client state."""
        self.session_id = None
        self.messages = []
        self.stimulus = SMART_HOME_STIMULI[0]

@pytest.fixture
def smart_home_client(created_smart_home_project_slug: str):
    """Fixture providing a smart home test client."""
    client = SmartHomeTestClient(project_slug=created_smart_home_project_slug)
    yield client
    client.reset()

# ======================================================================
#  5. VALUES-LIMIT TESTING FIXTURES
# ======================================================================

# --- Existing VALUES-LIMIT Fixtures (for test_values_limit_functionality.py) ---

@pytest.fixture(scope="module")
def created_values_limit_project_slug():
    """
    Creates a special project for testing the values limit functionality.
    Uses a low limit (n_values_max=2) for faster testing.
    """
    try:
        print("\nCreating values limit test project...")
        project_data = {
            "topic": "Values Limit Testing",
            "description": "Test project for values limit functionality",
            "stimuli": ["Testing stimulus for values limit"],
            "n_stimuli": 1,
            "api_key": SMART_HOME_CONFIG["openai_api_key"],  # Use Academic Cloud for tests
            "base_url": SMART_HOME_CONFIG["base_url"],
            "model": SMART_HOME_CONFIG["model"],
            "n_values_max": 2,  # LOW: For quick limit tests
            "elevenlabs_api_key": SMART_HOME_CONFIG["elevenlabs_api_key"],  # Added required field
            "max_retries": SMART_HOME_CONFIG["max_retries"],  # Added required field
            "voice_enabled": False,  # Added optional fields
            "advanced_voice_enabled": False,
            "tree_enabled": True
        }
        resp = requests.post("http://localhost:8000/test-project", json=project_data)
        
        if not resp.ok:
            print(f"❌ HTTP {resp.status_code}: {resp.text}")
            try:
                error_detail = resp.json()
                print(f"Error details: {error_detail}")
            except:
                pass
        
        resp.raise_for_status()
        generated_slug = resp.json().get("slug")
        print(f"✅ Values limit test project created: {generated_slug} (Limit: 2)")
        return generated_slug
    except Exception as e:
        pytest.fail(f"⚠️ Error creating values limit project: {e}")

# --- SPECIFIC PROJECTS FOR VALUES-LIMIT TEST CASES ---

@pytest.fixture(scope="module")
def created_project_single_value():
    """Creates a project with n_values_max=1 and returns its slug."""
    try:
        print("\nCreating test project with max_values=1...")
        project_data = {
            "topic": "Values Limit Testing",
            "description": "Project for value limit tests (Limit=1)",
            "stimuli": ["Value-Limit-Test"],
            "n_stimuli": 1,
            "api_key": INTERVIEW_CONFIG["openai_api_key"],
            "base_url": INTERVIEW_CONFIG["base_url"],
            "model": INTERVIEW_CONFIG["model"],
            "n_values_max": 1,  # LIMIT: 1 Value max
            "elevenlabs_api_key": INTERVIEW_CONFIG["elevenlabs_api_key"],  # Added required field
            "max_retries": INTERVIEW_CONFIG["max_retries"],  # Added required field
            "voice_enabled": False,  # Added optional fields
            "advanced_voice_enabled": False,
            "tree_enabled": True
        }
        resp = requests.post("http://localhost:8000/test-project", json=project_data)
        resp.raise_for_status()
        generated_slug = resp.json().get("slug")
        print(f"✅ Test project with max_values=1 created: {generated_slug}")
        return generated_slug
    except Exception as e:
        pytest.fail(f"⚠️ Error: {e}")

@pytest.fixture(scope="module")
def created_project_unlimited():
    """Creates a project with n_values_max=-1 (unlimited) and returns its slug."""
    try:
        print("\nCreating test project with max_values=-1 (unlimited)...")
        project_data = {
            "topic": "Unlimited Values Testing",
            "description": "Project for unlimited values tests",
            "stimuli": ["Unlimited Values Test"],
            "n_stimuli": 1,
            "api_key": INTERVIEW_CONFIG["openai_api_key"],
            "base_url": INTERVIEW_CONFIG["base_url"],
            "model": INTERVIEW_CONFIG["model"],
            "n_values_max": -1,  # UNLIMITED: -1 = no limit
            "elevenlabs_api_key": INTERVIEW_CONFIG["elevenlabs_api_key"],  # Added required field
            "max_retries": INTERVIEW_CONFIG["max_retries"],  # Added required field
            "voice_enabled": False,  # Added optional fields
            "advanced_voice_enabled": False,
            "tree_enabled": True
        }
        resp = requests.post("http://localhost:8000/test-project", json=project_data)
        resp.raise_for_status()
        generated_slug = resp.json().get("slug")
        print(f"✅ Test project with unlimited values created: {generated_slug}")
        return generated_slug
    except Exception as e:
        pytest.fail(f"⚠️ Error: {e}")

# --- Existing Values-Limit-Test-Client ---
class ValuesLimitTestClient:
    """Test client specifically for values limit tests."""
    
    def __init__(self, project_slug: str):
        self.session_id = None
        self.topic = "Values Limit Testing"
        self.stimulus = "Testing stimulus for values limit"
        self.messages = []
        self.project_slug = project_slug
        self.values_count = 0
        self.values_max = 2
        self.values_reached = False

    def send_message(self, message_content: str, print_response: bool = True) -> Dict[str, Any]:
        """
        Sends a message and tracks values count.
        
        Args:
            message_content: Message to send
            print_response: Whether to print response
            
        Returns:
            API response data
        """
        self.messages.append({"role": "user", "content": message_content})
        payload = {
            "template_name": "queue_laddering",
            "template_vars": {"topic": self.topic, "stimulus": self.stimulus},
            "message": message_content,
            "session_id": self.session_id,
            "projectSlug": self.project_slug,
            "stimulus": self.stimulus
        }
        try:
            print(f"\nVALUES-LIMIT-TEST | Session: {self.session_id} | Count: {self.values_count}/{self.values_max}")
            resp = requests.post(SMART_HOME_CONFIG["api_url"], json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            
            # Session-ID Update
            if "Next" in data and "session_id" in data["Next"]:
                self.session_id = data["Next"]["session_id"]
            elif "session_id" in data:
                self.session_id = data["session_id"]

            self.messages.append({"role": "assistant", "content": data["Next"]["NextQuestion"]})
            
            # Update Values-Status
            if "Next" in data:
                self.values_count = data["Next"].get("ValuesCount", self.values_count)
                self.values_max = data["Next"].get("ValuesMax", self.values_max)
                self.values_reached = data["Next"].get("ValuesReached", False)
                completion_reason = data["Next"].get("CompletionReason")
                end_of_interview = data["Next"].get("EndOfInterview", False)
                
                print(f"VALUES UPDATE: {self.values_count}/{self.values_max} | Reached: {self.values_reached}")
                if end_of_interview:
                    print(f"🏁 INTERVIEW ENDED: Reason={completion_reason}")
            
            return data
        except Exception as e:
            print(f"❌ Error: {e}")
            raise

    def reset(self):
        """Reset the client state."""
        self.session_id = None
        self.messages = []
        self.values_count = 0
        self.values_reached = False

@pytest.fixture
def values_limit_client(created_values_limit_project_slug: str):
    """Fixture providing a values limit test client."""
    client = ValuesLimitTestClient(project_slug=created_values_limit_project_slug)
    yield client
    client.reset()

# --- SPECIFIC TEST CLIENTS FOR VALUES-LIMIT TESTS ---

class SpecificValuesLimitTestClient:
    """Extended test client for values limit tests with configurable limits."""
    
    def __init__(self, project_slug: str, topic: str, stimulus: str, expected_max: int):
        self.session_id = None
        self.topic = topic
        self.stimulus = stimulus
        self.messages = []
        self.project_slug = project_slug
        self.values_count = 0
        self.values_max = expected_max
        self.values_reached = False

    def send_message(self, message_content: str) -> Dict[str, Any]:
        """
        Sends a message and tracks values with custom limits.
        
        Args:
            message_content: Message to send
            
        Returns:
            API response data
        """
        self.messages.append({"role": "user", "content": message_content})
        payload = {
            "template_name": "queue_laddering",
            "template_vars": {"topic": self.topic, "stimulus": self.stimulus},
            "message": message_content,
            "session_id": self.session_id,
            "projectSlug": self.project_slug,
            "stimulus": self.stimulus
        }
        try:
            print(f"\nVALUES-TEST | Session: {self.session_id} | Count: {self.values_count}/{self.values_max}")
            resp = requests.post(INTERVIEW_CONFIG["api_url"], json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            
            # Session-ID Update
            if "Next" in data and "session_id" in data["Next"]:
                self.session_id = data["Next"]["session_id"]
            elif "session_id" in data:
                self.session_id = data["session_id"]

            self.messages.append({"role": "assistant", "content": data["Next"]["NextQuestion"]})
            
            # Update Values-Status
            if "Next" in data:
                self.values_count = data["Next"].get("ValuesCount", self.values_count)
                self.values_max = data["Next"].get("ValuesMax", self.values_max)
                self.values_reached = data["Next"].get("ValuesReached", False)
                completion_reason = data["Next"].get("CompletionReason")
                end_of_interview = data["Next"].get("EndOfInterview", False)
                
                print(f"VALUES UPDATE: {self.values_count}/{self.values_max} | Reached: {self.values_reached}")
                if end_of_interview:
                    print(f"🏁 INTERVIEW ENDED: Reason={completion_reason}")
            
            return data
        except Exception as e:
            print(f"❌ Error: {e}")
            raise

    def reset(self):
        """Reset the client state."""
        self.session_id = None
        self.messages = []
        self.values_count = 0
        self.values_reached = False

@pytest.fixture
def values_limit_client_single(created_project_single_value: str):
    """Client with max_values=1"""
    client = SpecificValuesLimitTestClient(
        project_slug=created_project_single_value,
        topic="Values Limit Testing",
        stimulus="Value-Limit-Test",
        expected_max=1
    )
    yield client
    client.reset()

@pytest.fixture
def values_limit_client_unlimited(created_project_unlimited: str):
    """Client with max_values=-1 (unlimited)"""
    client = SpecificValuesLimitTestClient(
        project_slug=created_project_unlimited,
        topic="Unlimited Values Testing",
        stimulus="Unlimited Values Test",
        expected_max=-1
    )
    yield client
    client.reset()