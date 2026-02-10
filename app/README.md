# Backend Application

This backend application powers a structured interview system built on **means-end chain theory** and supported by **Large Language Models (LLMs)**. It processes user responses, identifies key elements, and builds a **means-end chain tree** to represent relationships between ideas, attributes, consequences, and values.

---

## Overview

The system provides:
- A **FastAPI-based backend** with modular architecture  
- Secure authentication and project management  
- A configurable **interview engine** that dynamically adapts to user responses  
- Integration with multiple **LLM providers** for question generation and analysis  
- Structured persistence in a **PostgreSQL database**  

---

## Application Structure
```bash
app/
├── __init__.py
├── main.py                 # FastAPI application entry point
├── models.py               # Pydantic response models
├── auth/                   # Authentication services
│   ├── auth_util.py        
│   └── encryption_service.py 
├── db/                     # Database components
│   ├── base.py             # SQLAlchemy base classes
│   ├── config.py           
│   ├── models_*.py         
│   └── session.py          
├── interview/              # Core interview engine (detailed in separate README)
│   ├── analysis/           
│   ├── chat_state/         
│   ├── interview_tree/     
│   └── ...                 
├── llm/                    # LLM integration
│   ├── client.py           
│   ├── structured_output_manager.py 
│   ├── template_store.py   
│   └── templates/          
├── routers/                # API endpoints
│   ├── auth.py             
│   ├── chat.py             
│   ├── project.py          
│   └── ...                 
└── schemas/                # Request/response schemas
    ├── schemas_auth.py     
    └── schemas_user.py  
```

---

## Core System Components

### FastAPI Application (`main.py`)
- Configures middleware (CORS, logging)  
- Registers API routers  
- Initializes database schema  
- Provides health/debug endpoints  

### Database Layer (`/db`)
- **ORM Models**: SQLAlchemy-based schema  
- **Session Management**: Async session and pooling  
- **Config**: Environment-based database connection  

### Authentication (`/auth`)
- **JWT authentication** with role-based access  
- **Password encryption** and verification  
- **Access control** for protected routes  

### LLM Integration (`/llm`)
- Generic client for multiple providers (OpenAI, Groq, etc.)  
- **Template management** for prompts  
- **Structured output parsing** for JSON responses  
- **Token management** with retries and error handling  

### Interview Engine (`/interview`)
- Analyzes user responses  
- Builds and updates interview trees  
- Generates follow-up questions  
- Manages session and state progression  
- See [interview/README.md](interview/README.md) for details  

### API Routes (`/routers`)
- `chat.py`: Interview conversation endpoints  
- `project.py`: Project configuration and management  
- `auth.py`: User management and authentication  
- `voice.py`: Voice integration (optional)  
- `session.py`: Session persistence and retrieval  

---

## Key Workflows

### 1. Interview Workflow
1. Client connects via `/interview/chat`.  
2. System initializes a new session.  
3. Each user response is processed:  
   - Elements identified (`element_analyzer.py`)  
   - Tree updated (`tree_update_handlers`)  
   - Next question generated (`question_generator.py`)  
4. Response returned to client.  

### 2. Project Management
- Admin creates projects via `/project` endpoints.  
- Stored in database with configurable parameters:  
  - Topic, stimuli, maximum values  
  - LLM model and API keys  
  - Voice settings  

### 3. Authentication Flow
- User registers via `/auth/register` (password encrypted).  
- Login via `/auth/login` returns JWT token.  
- Token required for secure API access.  

---

## Configuration

The application is configured via **environment variables**:
- Database connection (PostgreSQL)  
- LLM provider API keys  
- Authentication secrets  
- CORS origins  
- Logging levels  

---

## Integration Points

- **Frontend**: JSON REST APIs, CORS enabled, WebSocket support for real-time updates  
- **LLM Providers**: Multiple backends, token limit management, structured response parsing  
- **Database**: PostgreSQL with async SQLAlchemy and migrations  

---

## Testing

Tests are organized in `/tests`:
- **Unit tests**: For isolated components  
- **Integration tests**: For workflows (interview, project, auth)  
- **Fixtures**: For database and LLM mocking  

