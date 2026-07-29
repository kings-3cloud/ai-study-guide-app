# Implementation Phases & GitHub Copilot Prompts
Each prompt below is self-contained — paste it directly into GitHub Copilot Agent mode.
```

```
## Phase 1 — Project Setup

### Prompt 1 — Scaffold project structure + requirements
```
I'm building a Personal Study Assistant multi-agent app in Python using Azure AI Agent Service (azure-ai-projects SDK) and a custom MCP server. The project root is the current workspace.

Create the following folder and file structure (empty files are fine):
- agents/orchestrator.py
- agents/content_agent.py
- agents/quiz_agent.py
- agents/progress_agent.py
- mcp_server/server.py
- mcp_server/tools/fetch_url.py
- mcp_server/tools/fetch_pdf.py
- mcp_server/tools/quiz_tools.py
- mcp_server/tools/progress_tools.py
- data/progress/.gitkeep
- main.py
- config.py
- .env.example

Then create requirements.txt with these dependencies:
azure-ai-projects, azure-ai-agents, azure-identity, httpx, PyPDF2, mcp, python-dotenv, pydantic
```

### Prompt 2 — Config and .env setup
```
In config.py, create a Settings class using pydantic BaseSettings that loads from .env. It must include:
- PROJECT_CONNECTION_STRING: str  (Azure AI Foundry project connection string)
- AZURE_OPENAI_DEPLOYMENT_GPT4O: str = "gpt-4o"
- AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI: str = "gpt-4o-mini"
- PROGRESS_DATA_DIR: str = "data/progress"
- DEFAULT_USER_ID: str = "default_user"

Also populate .env.example with placeholder values and comments explaining each variable.
```

## Phase 2 — MCP Server & Tools

### Prompt 3 — MCP server base
```
In mcp_server/server.py, create a Python MCP server using the `mcp` library with stdio transport.
- Import and register all tools from the tools/ submodules: fetch_url, fetch_pdf, quiz_tools, progress_tools
- Name the server "study-assistant-mcp"
- Add a server entry point under `if __name__ == "__main__"` using mcp.run()
- Add a __init__.py to the mcp_server package
```

### Prompt 4 — fetch_url_content tool
```
In mcp_server/tools/fetch_url.py, implement a tool function named `fetch_url_content` for the MCP server.
- Parameter: url (str)
- Use httpx with a 10-second timeout to GET the URL
- Strip HTML tags using a simple regex or html.parser to return plain text
- Truncate output to 8000 characters max
- Return the cleaned text as a string
- Register it as an MCP tool using the @mcp.tool() decorator
- Handle network errors gracefully and return an error message string on failure
```

### Prompt 5 — fetch_pdf_content tool
```
In mcp_server/tools/fetch_pdf.py, implement a tool function named `fetch_pdf_content` for the MCP server.
- Parameter: file_path (str)
- Use PyPDF2 PdfReader to extract text from all pages
- Join page texts with newlines
- Truncate output to 8000 characters max
- Return the extracted text as a string
- Register as @mcp.tool()
- Handle FileNotFoundError and PDF parsing errors gracefully
```

### Prompt 6 — generate_quiz tool
```
In mcp_server/tools/quiz_tools.py, implement a tool named `generate_quiz` for the MCP server.
- Parameters: content (str), num_questions (int), question_types (list[str] = ["multiple_choice", "true_false", "short_answer"])
- This tool does NOT call an LLM — it creates a structured quiz template dict with the content and parameters, assigns a uuid quiz_id, records a created_at timestamp, and saves it as a JSON file in data/progress/quizzes/
- Return the quiz dict as a JSON string so the calling agent can populate the actual questions
- Register as @mcp.tool()
```

### Prompt 7 — save_progress and get_progress tools
```
In mcp_server/tools/progress_tools.py, implement two MCP tools:

1. save_progress(user_id: str, activity_type: str, data: dict) -> str
   - Load or create data/progress/{user_id}.json
   - Append a new entry: { "timestamp": ISO datetime, "activity_type": activity_type, "data": data }
   - Save back to file
   - Return a confirmation message string

2. get_progress(user_id: str) -> str
   - Load data/progress/{user_id}.json
   - If file doesn't exist, return a "no progress found" message
   - Return the full progress history as a JSON string

Register both as @mcp.tool(). Handle file I/O errors gracefully.
```

## Phase 3 — Azure AI Foundry Agent Creation

### Prompt 8 — Content Summarizer Agent
```
In agents/content_agent.py, write a function `create_or_get_content_agent(project_client)` that:
- Uses AIProjectClient from azure-ai-projects
- Creates an agent named "content-summarizer" with model from config AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI
- Sets the following instructions:
  "You are a content summarization specialist. When given a URL, use fetch_url_content to retrieve the page text. When given a file path, use fetch_pdf_content to extract PDF text. Structure every summary into four sections: (1) Topic Overview, (2) Key Concepts as bullet list, (3) Important Details, (4) Suggested Learning Objectives. Keep summaries under 500 words unless asked for more. After every summary, suggest 3-5 quiz topics."
- Attaches MCP tools: fetch_url_content and fetch_pdf_content (connected via MCP server config)
- If an agent with the same name already exists, retrieve and return it instead of creating a duplicate
- Return the agent object
```

### Prompt 9 — Quiz Generator Agent
```
In agents/quiz_agent.py, write a function `create_or_get_quiz_agent(project_client)` that:
- Creates an agent named "quiz-generator" with model from config AZURE_OPENAI_DEPLOYMENT_GPT4O
- Sets the following instructions:
  "You are an expert educational quiz creator. Generate quizzes from provided content or topics. Always create a balanced mix: 60% multiple choice (4 options labeled A–D), 20% true/false, 20% short answer. For every question include the correct answer and a one-sentence explanation. Default to 5 questions unless specified. Use the generate_quiz tool to structure and save quiz data before presenting it. After the user answers, score their responses."
- Attaches MCP tool: generate_quiz
- Implements create-or-retrieve pattern (check existing agents by name)
- Return the agent object
```

### Prompt 10 — Progress Tracker Agent
```
In agents/progress_agent.py, write a function `create_or_get_progress_agent(project_client)` that:
- Creates an agent named "progress-tracker" with model from config AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI
- Sets the following instructions:
  "You are a study progress tracking specialist. Use save_progress to log every study activity (topics read, quizzes taken, scores). Use get_progress to retrieve a user's history. Always report: topics studied, average quiz score, best and worst topics, and current study streak. Be encouraging — celebrate milestones. If a user has weak topics (score below 60%), recommend re-studying that content."
- Attaches MCP tools: save_progress, get_progress
- Implements create-or-retrieve pattern
- Return the agent object
```

### Prompt 11 — Orchestrator Agent
```
In agents/orchestrator.py, write a function `create_or_get_orchestrator(project_client, content_agent, quiz_agent, progress_agent)` that:
- Creates an agent named "study-orchestrator" with model from config AZURE_OPENAI_DEPLOYMENT_GPT4O
- Sets the following instructions:
  "You are a personal study assistant orchestrator. Delegate to the right specialist: (1) URL or PDF provided → Content Summarizer Agent, (2) Quiz requested → Quiz Generator Agent, (3) Progress/history asked → Progress Tracker Agent. For multi-step requests like 'study then quiz me', chain agents in order. Greet the user at the start and ask what they want to study today."
- Connects the other three agents as tools using the connected_agents / agent_tool pattern from azure-ai-agents
- Implements create-or-retrieve pattern
- Return the agent object
```

## Phase 4 — Conversation Loop

### Prompt 12 — Multi-turn conversation loop in main.py
```
In main.py, implement the main multi-turn conversation loop:
- Load config from config.py
- Authenticate using DefaultAzureCredential and create an AIProjectClient with PROJECT_CONNECTION_STRING
- Start the MCP server as a subprocess (mcp_server/server.py) so tools are available
- Call create_or_get_* functions from all four agent modules to provision or retrieve agents
- Create a new thread using project_client.agents.threads
- Enter a while loop: prompt user for input, exit on "quit"/"exit"
- Send each user message to the orchestrator agent via the thread
- Poll the run until status is "completed" or "failed"
- Print the latest assistant message from the thread
- Gracefully shut down the MCP server subprocess on exit
Use azure-ai-projects SDK patterns throughout. Add clear console output showing which agent is responding.
```
## Phase 5 — Verification

### Prompt 13 — Integration test script
```
Create a file tests/test_integration.py that runs an end-to-end smoke test:
1. Starts the MCP server subprocess
2. Tests fetch_url_content with https://en.wikipedia.org/wiki/Machine_learning
3. Tests generate_quiz with a sample content string (5 questions)
4. Tests save_progress with a dummy user_id "test_user" and sample quiz result data
5. Tests get_progress for "test_user" and asserts the saved entry appears
6. Prints PASS/FAIL for each test
Do not use any testing frameworks — plain Python with assert statements.
```

> ### Verification Checklist
1. Run python mcp_server/server.py — server starts without errors
1. Run python tests/test_integration.py — all 4 tool tests pass
1. Set PROJECT_CONNECTION_STRING in .env and run python main.py — agents provision in Azure AI Foundry portal
1. In Azure AI Foundry portal, confirm all 4 agents appear under your project
1. In the conversation loop: paste a Wikipedia URL → confirm summary response
1. Ask "quiz me on what I just read" → confirm 5 questions generated
1. Ask "show my progress" → confirm activity was saved and reported


> ### Decisions & Scope
- Agents live in Azure AI Foundry; the MCP server runs locally (or can be deployed later)
- Connected agents pattern used for orchestrator → specialist routing (not Semantic Kernel)
- No web UI — CLI conversation loop only in this plan
- User identity defaults to "default_user" configurable via .env
- PyPDF2 for PDF extraction (can be swapped for pdfplumber for better accuracy later)


> ### Further Considerations
1. MCP Server Transport: stdio (local subprocess) is used for dev simplicity. For production, switch to SSE transport so the MCP server can be deployed to Azure Container Apps and all 4 agents share one remote tool endpoint.
1. Agent Persistence: The "create-or-retrieve" pattern avoids duplicate agent provisioning on every run — important since Azure AI Foundry has per-agent billing and quotas.
1. Authentication: DefaultAzureCredential covers local dev (Azure CLI login) and production (Managed Identity) without code changes.


> I'm building a Personal Study Assistant multi-agent app in Python using Azure AI Agent Service (azure-ai-projects SDK) and a custom MCP server. The project root is the current workspace.
```
Create the following folder and file structure (empty files are fine):

agents/orchestrator.py
agents/content_agent.py
agents/quiz_agent.py
agents/progress_agent.py
mcp_server/server.py
mcp_server/tools/fetch_url.py
mcp_server/tools/fetch_pdf.py
mcp_server/tools/quiz_tools.py
mcp_server/tools/progress_tools.py
data/progress/.gitkeep
main.py
config.py
.env.example
Then create requirements.txt with these dependencies:
azure-ai-projects, azure-ai-agents, azure-identity, httpx, PyPDF2, mcp, python-dotenv, pydantic
```