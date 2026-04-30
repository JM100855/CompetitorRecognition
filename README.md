# CompetitorRecognition

CompetitorRecognition is an agentic web intelligence platform for discovering, scraping, and structuring web data into industry-specific relationship maps.

It combines search-driven source discovery, article extraction, schema-driven entity and relation extraction, vector retrieval, and graph storage so analysts can monitor a niche and query how companies, products, signals, and themes connect.

## What it does

- Discovers public web sources for a niche using DuckDuckGo search
- Scrapes and cleans article/page content with Trafilatura
- Extracts entities and relationships with Gemini using a structured JSON schema
- Stores document embeddings in ChromaDB for semantic retrieval
- Stores entity relationships in Kuzu for graph-style lookups
- Exposes the workflow through FastAPI and a Streamlit analyst UI

## Tech Stack

- `FastAPI`
- `Streamlit`
- `Trafilatura`
- `DuckDuckGo Search`
- `Gemini API`
- `ChromaDB`
- `Kuzu`
- `SQLite`

## Project layout

- `app/` contains the FastAPI app
- `app/api/` contains API routes
- `app/models/` contains SQLite models for runs, documents, entities, and relations
- `app/services/` contains search, scraping, extraction, vector, graph, and reporting logic
- `streamlit_app.py` provides the Streamlit analyst UI
- `app/templates/` and `app/static/` contain the lightweight FastAPI dashboard
- `scripts/seed_demo.py` creates a small sample dataset
- `data/` stores the local SQLite database

## Architecture

```mermaid
flowchart LR
    Analyst[Analyst] --> ST[Streamlit UI]
    Analyst --> API[FastAPI API]
    ST --> API
    API --> SEARCH[DuckDuckGo Discovery]
    API --> SCRAPE[Trafilatura Extraction]
    API --> GEMINI[Gemini Entity and Relation Extraction]
    API --> VECTOR[ChromaDB Vector Store]
    API --> GRAPH[Kuzu Knowledge Graph]
    API --> SQL[(SQLite Run Store)]
    VECTOR --> QUERY[Relationship-aware Retrieval]
    GRAPH --> QUERY
    QUERY --> ST
```

## Capture Flow

```mermaid
flowchart TD
    A[User enters niche and query] --> B[POST /api/intelligence/runs]
    B --> C[DuckDuckGo returns source candidates]
    C --> D[Fetch and clean page content]
    D --> E[Gemini extracts entities and relations]
    E --> F[Save raw docs and structured outputs in SQLite]
    F --> G[Upsert documents into ChromaDB]
    G --> H[Upsert entities and edges into Kuzu]
    H --> I[Return run summary, documents, entities, relations]
```

## Storage Model

```mermaid
erDiagram
    INTELLIGENCE_RUN ||--o{ WEB_DOCUMENT : captures
    INTELLIGENCE_RUN ||--o{ EXTRACTED_ENTITY : extracts
    INTELLIGENCE_RUN ||--o{ EXTRACTED_RELATION : extracts

    INTELLIGENCE_RUN {
        int id
        string niche
        string query
        string status
    }
    WEB_DOCUMENT {
        int id
        int run_id
        string title
        string url
    }
    EXTRACTED_ENTITY {
        int id
        int run_id
        string name
        string entity_type
    }
    EXTRACTED_RELATION {
        int id
        int run_id
        string source_entity
        string target_entity
        string relation_type
    }
```

## Local run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `.env` if you want Gemini extraction.

### Start FastAPI

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

### Start Streamlit

```powershell
streamlit run streamlit_app.py
```

Open `http://localhost:8501`.

## Basic workflow

1. Start the app.
2. Open the Streamlit UI.
3. Enter a niche and a search query.
4. Run an intelligence capture.
5. Review discovered documents, extracted entities, and graph relationships.
6. Use relationship-aware queries against the stored vector and graph indexes.

## API endpoints

- `GET /api/health`
- `GET /api/intelligence/runs`
- `GET /api/intelligence/runs/{run_id}`
- `POST /api/intelligence/runs`
- `POST /api/intelligence/query`
- `GET /api/niches`
- `POST /api/niches`
- `POST /api/niches/bootstrap`
- `POST /api/niches/{niche_id}/companies`
- `POST /api/companies/{company_id}/sources`
- `POST /api/jobs/run-daily`
- `GET /api/tasks`
- `POST /api/niches/{niche_id}/tasks`
- `GET /api/reports`
- `POST /api/tasks/{task_id}/run-basic-report`
- `POST /api/tasks/{task_id}/run-detailed-report`
- `GET /api/niches/{niche_id}/training-export`
