# Ladder Interview Engine
![Project Status: Active](https://img.shields.io/badge/Status-Active-green)

A backend system for conducting automated laddering interviews using Large Language Models (LLMs).  
This application builds on the LadderChat prototype and was extended as part of a team software development project at the Faculty of Economics, Institute of Business Informatics (WIN), Karlsruhe Institute of Technology (KIT).

---

## What Are Laddering Interviews?
Laddering is a qualitative research technique used to uncover consumer motivations and values.  
It explores the connections between:

- **Attributes** – Physical or abstract characteristics of a product or service  
- **Consequences** – Benefits or outcomes resulting from attributes  
- **Values** – Personal values or desired end states fulfilled by consequences  

The method follows a hierarchical means–end structure.  
This system automates the laddering process by guiding interviews with AI, analyzing responses, and dynamically building means–end chains.

---

## Setup Instructions

### Prerequisites
- Docker and Docker Compose  
- Node.js and npm (for frontend)  
- Python 3.11+ (for local development)  

### Backend Setup
1. Clone the repository  
```bash
git clone https://gitlab.kit.edu/kit/win/h-lab/research/ladderchat/backend.git
cd backend
```
2. Create a `.env` file in the root directory with the required configuration values
```bash
DB_USER=postgres
DB_PASSWORD=secret
DB_HOST=db
DB_PORT=5432
DB_NAME=laddering
JWT_SECRET_KEY=test
ENCRYPTION_KEY=your_encryption_key_here

# Optional LLM API keys
# OPENAI_API_KEY=your_openai_key
```
3. Start the backend using Docker Compose  

```bash
docker-compose up --build
```
The Docker Compose file used is:
```bash
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./app:/code/app
    env_file:
      - .env
    depends_on:
      - db
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: laddering
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### Frontend Setup
1. Clone the frontend repository (if not already done)
```bash
git clone https://gitlab.kit.edu/kit/win/h-lab/research/ladderchat/frontend.git
cd frontend
```
2. Install dependencies (once)
```bash
npm install
```
3. Start the development server
```bash
npm run dev
```
4. Access the application
Open your browser and navigate to http://localhost:3000

## Project Structure
### Backend (app/)
```bash
app/
├── auth/             # Authentication and authorization
├── db/               # Database models and connection handling
├── interview/        # Core interview engine
│   ├── analysis/     # Response analysis using LLMs
│   ├── chat_state/   # Interview state management
│   ├── handlers/     # Message and tree update handlers
│   ├── interview_tree/ # Tree data structure for means-end chains
│   └── questioning/  # Question generation
├── llm/              # LLM provider integration
│   └── templates/    # Prompt templates
├── routers/          # API endpoints
└── schemas/          # Request/response schemas
```
### Key Components
- **Interview Engine** – Manages the flow of laddering interviews  
- **LLM Integration** – Provides communication with multiple AI providers (e.g., OpenAI, Anthropic)  
- **Tree Structure** – Organizes identified elements into hierarchical means–end chains  
- **API Routes** – RESTful endpoints for frontend and client interaction  

### Test Structure (tests/)
```bash
tests/
├── unit/            # Unit tests for isolated components
└── integration/     # Integration tests for combined functionality
```
---

## API Documentation
Once the backend is running, API documentation is available at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)  
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)  

---

## Further Documentation
More detailed documentation can be found in the respective module folders:

- **Interview Engine**: `interview/README.md`  
- **Testing**: `tests/README.md`  

---

## License
This project was developed for research purposes at the Karlsruhe Institute of Technology (KIT), Institute of Business Informatics (WIN).  

---

## Contributors
This backend system was designed and implemented as part of a collaborative team project at KIT, Faculty of Economics, Institute of Business Informatics (WIN).  
