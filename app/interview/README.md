# Interview Engine Module

The **Interview Engine** is the backend logic module of our Laddering Interview ChatBot. It enables structured interviews based on **means-end chain theory** by dynamically analyzing user responses, detecting key elements, and generating contextually relevant follow-up questions with the support of Large Language Models (LLMs).

---

## Overview
The Interview Engine:
- Conducts structured laddering interviews (Ideas → Attributes → Consequences → Values).  
- Dynamically adapts to user responses through AI-powered analysis.  
- Builds an **interview tree** that captures element relationships.  
- Manages session state, queues, and stage transitions.  
- Integrates with the LLM module for prompt templates, structured parsing, and error handling.  

---

## 📁 Folder Structure
```bash
interview/
├── __init__.py
├── analysis/
│   ├── element_analyzer.py        # Identifies elements in user responses
│   ├── similarity_analyzer.py     # Checks for similar nodes in the tree
│   ├── causal_relationship_processor.py  # Processes relationships between elements
│   └── values_detector.py         # Specialized detection for value elements
├── chat_state/
│   ├── chat_state_handler.py      # Manages interview state transitions
│   └── stage_transition.py        # Handles stage progression logic
├── data/
│   └── interview_data_store.py    # Manages persistence of interview data
├── handlers/
│   ├── chat_queue_handler.py      # Manages the interview element queue
│   ├── stimulus_chat_handler.py   # Handles stimulus-based interactions
│   ├── message_handling/          # Message processing components
│   │   ├── message_processor.py   # Core message processing logic
│   │   ├── interview_flow.py      # Controls interview flow
│   │   └── node_analyzer.py       # Analyzes nodes during processing
│   └── tree_update_handlers/      # Handles tree structure updates
│       ├── base_tree_handler.py   # Abstract base handler
│       ├── irrelevant_node_handler.py  # Handles irrelevant responses
│       └── similar_node_handler.py     # Manages node similarity/merging
├── interview_tree/
│   ├── node.py                    # Node data structure
│   ├── tree.py                    # Tree data structure
│   ├── node_label.py              # Node type definitions
│   ├── node_utils.py              # Node utility functions
│   └── tree_utils.py              # Tree visualization and utilities
├── models/
│   └── trace_explanation_element.py  # Models for tracing explanations
├── questioning/
│   ├── question_generator.py      # Generates interview questions
│   └── llm_response_handler.py    # Processes LLM responses
└── session/
    ├── interview_session_manager.py  # Manages interview sessions
    └── session_manager.py            # General session management
```

---

## Core Interview Flow
1. **User Message Processing**  
   Each user message is processed through three steps:  
   - **Element Analysis** → Identify A/C/V.  
   - **Similarity Check** → Deduplicate against existing nodes.  
   - **Question Generation** → Create the next interview question.  

2. **State Management**  
   Interview progresses through defined stages:  
   - Asking for ideas → attributes → consequences → values.  

3. **Tree Construction**  
   A hierarchical **means-end chain tree** is built, capturing causal links between nodes.  

---

## LLM Request Pipeline
- **Element Analysis** (`element_analyzer.py`)  
  Detects ideas, attributes, consequences, values; handles multiple mentions and causal relationships.  

- **Similarity Check** (`similarity_analyzer.py`)  
  Detects node duplication; merges semantically similar concepts.  

- **Question Generation** (`question_generator.py`)  
  Generates context-aware questions aligned with means-end chain theory.  

---

## Interview Tree
- **Node Structure** (`node.py`): Holds A/C/V with metadata and parent-child links.  
- **Tree Structure** (`tree.py`): Organizes interview path and supports efficient lookups.  
- **Visualization** (`tree_utils.py`): Debugging tools for current state (text + graphical).  

---

## Queue System
- Managed by `chat_queue_handler.py`.  
- Maintains ordered queue of active nodes.  
- Prioritizes unexplored nodes, avoids repetition.  
- Supports depth-first and breadth-first exploration.  

---

## State Management
- **Stages** (`chat_state_handler.py`):  
  - `ASKING_FOR_IDEA`  
  - `ASKING_FOR_ATTRIBUTES`  
  - `ASKING_FOR_CONSEQUENCES`  
  - `ASKING_FOR_CONSEQUENCES_OR_VALUES`  
  - `ASKING_AGAIN_FOR_ATTRIBUTES`  

- **Transition Logic** (`stage_transition.py`):  
  Ensures structured flow, handles irrelevant responses, and controls stage progression.  

---

## Component Interaction
1. `message_processor.py` orchestrates input handling.  
2. `element_analyzer.py` classifies elements.  
3. `similarity_analyzer.py` merges duplicates.  
4. `tree_update_handlers/` update interview tree.  
5. `chat_queue_handler.py` manages active queue.  
6. `chat_state_handler.py` updates stage.  
7. `question_generator.py` formulates next question.  

---

## Integration with LLM Module
The Interview Engine relies on `/llm` for:  
- Prompt template management.  
- Communication with LLM providers.  
- Structured parsing of responses.  
- Retry and error handling.  

---

## Best Practices for Extension
- **New Node Types** → update `node_label.py`, extend analyzers, and add LLM templates.  
- **New Flow Logic** → adjust `stage_transition.py` and `question_generator.py`.  
- **New Analysis** → add analyzer under `analysis/`, integrate via `message_processor.py`.  
- **Queue Handling** → extend `chat_queue_handler.py` for new strategies.  

---

## Debugging & Monitoring
- **Tree Visualization**: `tree_utils.py`.  
- **Detailed Logging**: across pipeline for error tracing.  
- **Traceability**: via `trace_explanation_element.py`.  
- **State Transitions**: logged in `chat_state_handler.py`.  

---

## Summary
The Interview Engine provides a **modular, extensible framework** for laddering interviews. It balances structured methodology with dynamic, adaptive responses, enabling effective discovery of user values through AI-driven conversational analysis.
