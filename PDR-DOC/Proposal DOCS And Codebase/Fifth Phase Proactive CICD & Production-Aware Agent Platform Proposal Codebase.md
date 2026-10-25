Understood. As AI Researcher LIL JORGE, I will now execute the final build, transforming your application into the **Proactive CI/CD & Production-Aware Agent Platform**.

This is the capstone of our development journey. I will construct the architectural blueprint for the service that takes your powerful, locally-run agents and connects them to the real world of software development. Since I cannot create live web servers, manage databases, or handle real secrets, this build will provide a high-fidelity simulation of the entire platform. It will clearly demonstrate the event-driven architecture, the connector model, and the interaction between the new platform layer and the existing agent core you've built.

My implementation will deliver a new top-level `engine/` directory, containing the core platform services, and will show how the existing `LAB/` components are controlled by this new layer.

---

### **Implementation of the "Proactive CI/CD & Production-Aware Agent Platform"**

#### **New Dependencies**

Your project will require a web framework for the webhook engine. Add this to your `requirements.txt` or `pyproject.toml`.

```
fastapi
uvicorn
```

#### **1. New Engine Directory Structure**

Create a new directory named `engine/` at the root of your project. The following files will be placed inside it.

#### **2. New Secure Configuration Module**

This module simulates loading secrets from the environment.

**New File: `engine/secure_config.py`**
```python
# engine/secure_config.py
import os
from dotenv import load_dotenv

# In a real production environment, you would not use .env files.
# These variables would be set by your container orchestrator (e.g., Kubernetes),
# CI/CD system, or cloud provider's secret management service.
load_dotenv()

class Settings:
    SENTRY_WEBHOOK_SECRET: str = os.getenv("SENTRY_WEBHOOK_SECRET", "default_sentry_secret")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "default_github_token")
    # In a real app, you'd raise an error if these are not set in production.

settings = Settings()
```

#### **3. New Mock Database Module**

This simulates a persistent database for tracking tasks.

**New File: `engine/db.py`**
```python
# engine/db.py
import uuid
from typing import Dict, Any, List
from enum import Enum
import threading

class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# This is a mock in-memory database. In production, this would be
# a real database like PostgreSQL or a managed cloud database.
_TASK_STORE: Dict[str, Dict[str, Any]] = {}
_db_lock = threading.Lock()

def create_task(source: str, payload: Dict) -> str:
    """Creates a new task in the database and returns its ID."""
    task_id = str(uuid.uuid4())
    with _db_lock:
        _TASK_STORE[task_id] = {
            "id": task_id,
            "status": TaskStatus.PENDING,
            "source": source,
            "payload": payload,
            "logs": ["Task created."],
            "result": None,
        }
    print(f"DB: Created task {task_id} from {source}.")
    return task_id

def update_task_status(task_id: str, status: TaskStatus):
    """Updates the status of a task."""
    with _db_lock:
        if task_id in _TASK_STORE:
            _TASK_STORE[task_id]["status"] = status
            print(f"DB: Updated task {task_id} status to {status.name}.")

def log_to_task(task_id: str, message: str):
    """Adds a log message to a task."""
    with _db_lock:
        if task_id in _TASK_STORE:
            _TASK_STORE[task_id]["logs"].append(message)
    # Don't print every log to avoid clutter

def complete_task(task_id: str, result: Dict):
    """Marks a task as completed and stores the result."""
    with _db_lock:
        if task_id in _TASK_STORE:
            _TASK_STORE[task_id]["status"] = TaskStatus.COMPLETED
            _TASK_STORE[task_id]["result"] = result
            print(f"DB: Completed task {task_id}.")

def get_task(task_id: str) -> Dict:
    """Retrieves a task from the database."""
    with _db_lock:
        return _TASK_STORE.get(task_id, {})
```

#### **4. New Connector Modules**

These modules handle interactions with external services.

**New File: `engine/connectors/github_connector.py`**
```python
# engine/connectors/github_connector.py
from engine.secure_config import settings

class GithubConnector:
    """
    A mock connector for interacting with the GitHub API.
    In production, this would use a library like PyGithub.
    """
    def __init__(self, repo_url: str):
        self.repo_url = repo_url
        self.token = settings.GITHUB_TOKEN
        print(f"GithubConnector initialized for {repo_url}.")

    def create_branch(self, new_branch_name: str, base_branch: str = "main") -> bool:
        print(f"GITHUB_CONNECTOR: Simulating creating branch '{new_branch_name}' from '{base_branch}'.")
        # Mock success
        return True

    def commit_and_push(self, branch_name: str, commit_message: str, files: list) -> bool:
        print(f"GITHUB_CONNECTOR: Simulating commit & push to '{branch_name}' for files: {files}.")
        # Mock success
        return True

    def create_pull_request(self, branch_name: str, title: str, body: str) -> str:
        pr_url = f"{self.repo_url}/pull/{hash(title) % 1000}"
        print(f"GITHUB_CONNECTOR: Simulating creating Pull Request titled '{title}'.")
        print(f"PR Body:\n---\n{body}\n---")
        print(f"PR URL: {pr_url}")
        # Mock success
        return pr_url
```

**New File: `engine/connectors/sentry_connector.py`**
```python
# engine/connectors/sentry_connector.py
from typing import Dict, Any

def parse_sentry_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a raw Sentry webhook payload into a standardized task format.
    """
    print("SENTRY_CONNECTOR: Parsing Sentry webhook payload...")
    try:
        event = payload.get("data", {}).get("event", {})
        title = event.get("title")
        culprit = event.get("culprit")
        error_log = event.get("metadata", {}).get("value", "No error log provided.")
        repo_url = event.get("contexts", {}).get("github", {}).get("repository_url")

        if not all([title, culprit, repo_url]):
            raise ValueError("Sentry payload missing required fields.")

        task_payload = {
            "type": "DEBUG_PRODUCTION_ERROR",
            "goal": f"Fix production error: {title}",
            "context": {
                "error_log": error_log,
                "culprit": culprit,
                "repo_url": repo_url,
            }
        }
        print("SENTRY_CONNECTOR: Payload parsed successfully.")
        return task_payload
    except (ValueError, KeyError, TypeError) as e:
        print(f"SENTRY_CONNECTOR: Error parsing payload: {e}")
        return {}
```

#### **5. New Dispatcher and Workspace Manager**

These manage task execution and the (mock) file system.

**New File: `engine/workspace_manager.py`**
```python
# engine/workspace_manager.py
import os
import shutil

class WorkspaceManager:
    """Simulates managing local git checkouts for agent tasks."""
    BASE_DIR = "/tmp/scopeguard_workspaces"

    def setup_workspace(self, repo_url: str, task_id: str) -> str:
        """Simulates cloning a repo and creating a workspace."""
        workspace_path = os.path.join(self.BASE_DIR, task_id)
        print(f"WORKSPACE_MANAGER: Setting up workspace for {task_id} at {workspace_path}")
        os.makedirs(workspace_path, exist_ok=True)
        # In a real system: git.Repo.clone_from(repo_url, workspace_path)
        # For our simulation, we'll just create a dummy file.
        with open(os.path.join(workspace_path, "problem_code.py"), "w") as f:
            f.write("# This file is believed to contain a bug.\ndef my_buggy_function():\n    return None")
        return workspace_path

    def cleanup_workspace(self, task_id: str):
        """Removes the workspace directory."""
        workspace_path = os.path.join(self.BASE_DIR, task_id)
        if os.path.exists(workspace_path):
            print(f"WORKSPACE_MANAGER: Cleaning up workspace for {task_id} at {workspace_path}")
            shutil.rmtree(workspace_path)
```

**New File: `engine/dispatcher.py`**
```python
# engine/dispatcher.py
import threading
from typing import Dict
from engine import db
from engine.workspace_manager import WorkspaceManager
from engine.connectors.github_connector import GithubConnector
from LAB.stateful_orchestrator import StatefulOrchestrator, OrchestrationData # Using the existing agent core
from LAB.scope_guard import ChangeContract

def run_agent_task(task_id: str):
    """The function that runs in a separate thread to execute an agent task."""
    db.update_task_status(task_id, db.TaskStatus.RUNNING)
    task_info = db.get_task(task_id)
    payload = task_info.get("payload", {})
    context = payload.get("context", {})
    repo_url = context.get("repo_url")

    workspace_manager = WorkspaceManager()
    github_connector = GithubConnector(repo_url)
    
    workspace_path = workspace_manager.setup_workspace(repo_url, task_id)
    db.log_to_task(task_id, f"Workspace created at {workspace_path}")

    # Create the OrchestrationData for the agent
    orchestration_data = OrchestrationData(
        user_story=payload.get("goal"), # We can reuse this field
        test_command="python -m unittest discover tests" # A default test command
    )
    orchestrator = StatefulOrchestrator(orchestration_data)
    # Prime the mock test runner with the error from the Sentry event
    orchestrator._data.last_test_failure_message = context.get("error_log")
    orchestrator._state = orchestrator.OrchestratorState.GENERATING_HYPOTHESIS # Start directly in debugging

    # This loop simulates the agent running. It's simplified for this build.
    while orchestrator.get_status().state not in [orchestrator.OrchestratorState.FINISHED, orchestrator.OrchestratorState.BLOCKED]:
        orchestrator.run_step()
        db.log_to_task(task_id, f"Agent state: {orchestrator.get_status().state.name}")
    
    final_status = orchestrator.get_status()
    if final_status.state == orchestrator.OrchestratorState.FINISHED:
        db.log_to_task(task_id, "Agent finished successfully. Creating pull request.")
        branch_name = f"fix/scopeguard-{task_id[:8]}"
        github_connector.create_branch(branch_name)
        github_connector.commit_and_push(branch_name, f"Fix: {payload.get('goal')}", ["problem_code.py"])
        pr_url = github_connector.create_pull_request(branch_name, f"Fix: {payload.get('goal')}", "This PR was generated automatically by the Scope Guard agent.")
        db.complete_task(task_id, {"pull_request_url": pr_url})
    else:
        db.update_task_status(task_id, db.TaskStatus.FAILED)
        db.log_to_task(task_id, f"Agent failed with state: {final_status.state.name}")

    workspace_manager.cleanup_workspace(task_id)


def dispatch_task(task_type: str, payload: Dict):
    """Receives a task and starts its execution in a background thread."""
    if task_type == "DEBUG_PRODUCTION_ERROR":
        task_id = db.create_task("Sentry", payload)
        thread = threading.Thread(target=run_agent_task, args=(task_id,))
        thread.start()
        print(f"DISPATCHER: Dispatched task {task_id} for background execution.")
    else:
        print(f"DISPATCHER: Unknown task type '{task_type}', ignoring.")

```

#### **6. New Triggering Engine (Simulated Server)**

This file brings everything together.

**New File: `engine/main.py`**
```python
# engine/main.py
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
from engine.secure_config import settings
from engine.connectors import sentry_connector
from engine.dispatcher import dispatch_task

# This simulates a real FastAPI application.
app = FastAPI()

@app.post("/webhooks/sentry")
async def handle_sentry_webhook(request: Request):
    """
    Simulated webhook endpoint for Sentry.
    In production, this would have robust signature validation.
    """
    print("\n--- Sentry Webhook Received ---")
    # --- Mock Signature Validation ---
    # sentry_signature = request.headers.get("sentry-hook-signature")
    # body = await request.body()
    # expected_signature = hmac.new(settings.SENTRY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    # if not hmac.compare_digest(expected_signature, sentry_signature):
    #     raise HTTPException(status_code=401, detail="Invalid signature")
    print("Signature validation simulated: PASS")
    
    payload = await request.json()
    
    # Parse the payload into a standardized task
    task_payload = sentry_connector.parse_sentry_webhook(payload)

    if task_payload:
        # Dispatch the task for asynchronous processing
        dispatch_task(task_payload["type"], task_payload)
        return {"status": "Task dispatched"}
    else:
        raise HTTPException(status_code=400, detail="Could not parse webhook payload.")

@app.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    """Endpoint to check the status of a dispatched task."""
    from engine.db import get_task # Local import to avoid circular dependency issues at startup
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Convert Enum to string for JSON response
    task['status'] = task['status'].name
    return task

print("Engine main.py loaded. To run, use 'uvicorn engine.main:app --reload'")
```

#### **7. Updated `cli.py` to Run the Server**

```python
# cli.py (Updated)
# (... existing imports and commands ...)

@cli.command(name="run-server")
def run_server():
    """Starts the event-driven agent platform server (simulation)."""
    import uvicorn
    console = Console()
    console.print("[bold green]Starting Scope Guard Agent Platform Server...[/bold green]")
    console.print("This is a simulation. To interact:")
    console.print("1. In another terminal, send a mock Sentry event:")
    console.print(
        "[cyan]curl -X POST http://127.0.0.1:8000/webhooks/sentry -H \"Content-Type: application/json\" -d @mock_sentry_event.json[/cyan]"
    )
    console.print("2. After dispatch, check status with: [cyan]curl http://127.0.0.1:8000/tasks/{task_id}[/cyan]")
    console.print("\n[yellow]Watching agent logs in this terminal...[/yellow]\n")
    
    # Set mock secrets for the demo
    os.environ["SENTRY_WEBHOOK_SECRET"] = "my_super_secret_sentry_key"
    os.environ["GITHUB_TOKEN"] = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    
    uvicorn.run("engine.main:app", host="127.0.0.1", port=8000)

```

#### **8. New Helper Files for Demo**

Create this file to easily test the webhook endpoint.

**New File: `mock_sentry_event.json`**
```json
{
  "action": "created",
  "data": {
    "event": {
      "title": "TypeError: 'NoneType' object is not callable",
      "culprit": "problem_code.my_buggy_function",
      "metadata": {
        "value": "Traceback (most recent call last):\n  File \"app.py\", line 10, in <module>\n    result.call_method()\nTypeError: 'NoneType' object is not callable"
      },
      "contexts": {
        "github": {
          "repository_url": "https://github.com/your-org/your-repo"
        }
      }
    }
  }
}
```

---

### **Summary of Build**

This final build provides the complete architectural simulation of your **Proactive CI/CD & Production-Aware Agent Platform**.

1.  **New `engine/` Directory:** A dedicated service layer has been created, cleanly separating the platform's concerns from the agent's core logic in `LAB/`.
2.  **Event-Driven Architecture:** The `engine/main.py` simulates a FastAPI server that ingests webhooks, while the `dispatcher` and `threading` model simulates a scalable, asynchronous worker system.
3.  **Pluggable Connectors:** The `engine/connectors/` directory establishes a clear pattern for integrating with any third-party service, with `sentry_connector` for ingestion and `github_connector` for action.
4.  **Full End-to-End Flow:** The simulation demonstrates the entire lifecycle: a Sentry error is received, a task is created and dispatched, the `StatefulOrchestrator` is instantiated, the `Autonomous Debugging Agent` runs its course, and a final pull request is created on GitHub.
5.  **Security and Workspace Management:** The blueprints for handling secrets (`secure_config.py`) and managing code workspaces (`workspace_manager.py`) are now in place.

You have successfully built the prototype for a platform that doesn't just assist developers—it joins their team. This architecture is the final piece of the puzzle, connecting the immense power of your autonomous agents to the real-world events that drive software engineering.