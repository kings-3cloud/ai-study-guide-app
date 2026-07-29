## MCP Server Tools
| Tool |	Parameters |	Returns |	Library |
| ---   | --- | --- | --- |
| fetch_url_content |	url: str        |	cleaned page text   |	httpx
| fetch_pdf_content |	file_path: str  |	extracted text      |	PyPDF2
| generate_quiz     |	content: str, num_questions: int, question_types: list  |	structured quiz dict    |	stdlib
| save_progress     |	user_id: str, activity_type: str, data: dict            |	bool    |	stdlib (JSON)
| get_progress      |	user_id: str    |	progress history dict   |	stdlib (JSON)


## Project Structure
```
ai-study-guide-app/
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── content_agent.py
│   │   ├── quiz_agent.py
│   │   └── progress_agent.py
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── tools/
│   │       ├── fetch_url.py
│   │       ├── fetch_pdf.py
│   │       ├── quiz_tools.py
│   │       └── progress_tools.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── models.py          ← Pydantic request/response schemas
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── chat.py        ← POST /api/thread, POST /api/chat
│   │       ├── progress.py    ← GET /api/progress/{user_id}
│   │       └── files.py       ← POST /api/upload-pdf
│   ├── data/progress/
│   ├── main.py                ← FastAPI app entry point
│   ├── config.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html             ← Chat UI
│   ├── progress.html          ← Progress dashboard
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── app.js             ← Chat fetch calls + thread management
│       └── progress.js        ← Progress fetch + display
└── planning/
    └── prompts.md
```

## Architecture flow:
```
Browser (frontend/) → FastAPI (backend/main.py)
                          ↓
                   Azure AI Foundry Agents
                          ↓
                   MCP Server (subprocess)
                          ↓
                  data/progress/ (JSON files)
```

## API Endpoints
|   Method    | Endpoint  |	Purpose |
|   ---   | --- |   --- | 
| POST  |	/api/thread |   Create a new agent conversation thread → { thread_id }
| POST  |	/api/chat   |   	Send message, run orchestrator → { response, thread_id }
| GET   |	/api/progress/{user_id} |   	Fetch user's study history
| POST  |	/api/upload-pdf |   	Upload PDF file → { file_path } (used in next chat message)