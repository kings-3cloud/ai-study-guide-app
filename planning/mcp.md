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
├── agents/
│   ├── orchestrator.py        ← creates/retrieves Orchestrator agent
│   ├── content_agent.py       ← creates/retrieves Content Summarizer agent
│   ├── quiz_agent.py          ← creates/retrieves Quiz Generator agent
│   └── progress_agent.py      ← creates/retrieves Progress Tracker agent
├── mcp_server/
│   ├── server.py              ← MCP server entry point (stdio transport)
│   └── tools/
│       ├── fetch_url.py
│       ├── fetch_pdf.py
│       ├── quiz_tools.py
│       └── progress_tools.py
├── data/
│   └── progress/              ← JSON progress files per user
├── main.py                    ← multi-turn conversation loop
├── config.py                  ← centralized settings
├── requirements.txt
└── .env
```