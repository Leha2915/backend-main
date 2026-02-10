# Tests for the Interview Engine

This folder contains the test-suite for the **Interview Engine** (backend). The engine powers structured laddering interviews (attribute → consequence → value chains) via a conversational AI. This README documents test structure, how to run tests, configuration options and contribution guidelines.

---

## Table of Contents
- [Overview](#-overview)  
- [Test Structure](#-test-structure)  
- [Running Tests](#-running-tests)  
- [Configuration](#-configuration)  
  - [LLM Provider Configuration](#1-llm-provider-configuration)  
  - [Test Project Settings](#2-test-project-settings)  

---

## Overview
The tests in this directory validate that the Interview Engine can:

- conduct structured laddering interviews (A→C→V)
- manage sessions and multiple stimuli
- process user responses and detect elements (attributes, consequences, values)
- analyze causal relationships between elements
- handle irrelevant or very short responses robustly
- enforce configured limits (e.g., max values per chain)
- merge semantically similar nodes reliably

---

## Test Structure
tests/
├── conftest.py # Global fixtures and test configuration
├── integration/
│ ├── test_interview_workflow.py
│ ├── test_node_merging.py
│ ├── test_irrelevant_message_detection.py
│ ├── test_values_limit_functionality.py
│ ├── test_multi_element_response.py
│ ├── test_session_management.py
│ ├── test_cross_session_stimuli.py
│ └── test_queue_laddering_template.py
└── unit/
└── test_node_sharing.py


- `conftest.py` centralizes fixtures (mock LLM client, API endpoint, sample projects, DB session mocks).
- `integration/` contains end-to-end scenarios that can use the real backend (or mocked LLM endpoints).
- `unit/` contains small, fast tests for individual components.

---

## Running Tests

### Prerequisites
- Python 3.9+ (virtualenv recommended)  
- `pytest` installed (`pip install -r requirements-dev.txt`)  
- Docker (optional, used to run local backend service)  
- LLM API keys (set as env vars or configured in `conftest.py`)

### Common commands
- Run all tests (note: may trigger expensive LLM requests):

```bash
pytest
```
- Run a single integration test file:
```bash
pytest tests/integration/test_interview_workflow.py -q
```
- Run a single unit test:
```bash
pytest tests/unit/test_node_sharing.py -q
```

## Configuration
All test configuration is handled in `tests/conftest.py`. Two main configuration groups:

### 1. LLM Provider Configuration
Edit INTERVIEW_CONFIG (or supply env vars) to configure provider details:
```bash
INTERVIEW_CONFIG = {
    "api_url": "http://localhost:8000/interview/chat",
    "openai_api_key": "your-openai-api-key-here",
    "model": "gpt-4",
    "base_url": "https://api.openai.com/v1",
    "admin_key": "your-admin-key",
    "elevenlabs_api_key": "your-elevenlabs-key",
    "max_retries": 3
}
```
- Use local mock endpoints for fast CI-friendly runs.

### 2. Test Project Settings
You can create custom test projects to run through different flows:
```bash
project_data = {
    "topic": "Custom Test Topic",
    "description": "Test project for custom feature",
    "stimuli": ["Custom Stimulus 1", "Custom Stimulus 2"],
    "n_stimuli": 2,
    "api_key": "your-api-key",
    "base_url": "your-base-url",
    "model": "your-model-name",
    "n_values_max": 5,                  # -1 for unlimited
    "elevenlabs_api_key": "your-key",
    "max_retries": 3,
    "voice_enabled": True,
    "advanced_voice_enabled": False,
    "tree_enabled": True
}
```



