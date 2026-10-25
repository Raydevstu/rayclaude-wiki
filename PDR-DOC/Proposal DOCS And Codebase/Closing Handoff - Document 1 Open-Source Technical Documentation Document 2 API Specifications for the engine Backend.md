Excellent. My role now shifts from architect to enabler. I will draft the two foundational documents required to execute Phase II. The first is the public-facing technical documentation for the open-source libraries that will build our community. The second is the internal API specification for our backend engine, which will allow our frontend team to begin building the Mission Control UI.

This is the formal handoff.

---

### **Document 1: Open-Source Technical Documentation**

# ScopeGuard OS: A Framework for Reliable AI Engineering

## Introduction

The ScopeGuard OS project is an open-source library of Python tools designed to address the most critical failure point in AI-assisted software development: **trust**. While modern LLMs are incredibly powerful code generators, they often produce solutions that are over-scoped, untested, unmaintainable, or subtly broken.

ScopeGuard OS provides a suite of modular, "fail-closed" components—called **Guards**—that allow you to wrap your AI-driven workflows in a verifiable, evidence-based governance layer. Our philosophy is simple: **Don't just generate code; generate proof.**

This library empowers you to build AI agents that are not only powerful but also predictable, safe, and reliable.

## Core Principles

*   **Evidence-Driven:** Claims of success must be backed by verifiable evidence. An HTTP 200 status is not "done." A passing unit test is not a passing feature.
*   **Fail-Closed:** In the face of uncertainty, ambiguity, or risk, the default action is to halt and seek clarification, not to proceed with a risky assumption.
*   **Contract-Based:** All significant AI-driven actions are governed by an explicit, machine-readable `ChangeContract` that defines the goal, scope, and acceptance criteria *before* work begins.

## Installation

```bash
pip install scopeguard-os
```

## Core Components: The Guards

The library is composed of several independent but interoperable Guards. Here are some of the most important ones:

### 1. `ScopeGuard`

This is the foundational guard. It ensures an AI's changes adhere to a pre-defined scope.

*   **Purpose:** Prevents over-scoped changes and "scope creep."
*   **Input:** `ChangeContract`, a dataclass defining the allowed scope (files, layers, budget), and a tuple of `ChangedFile` objects representing the proposed changes.
*   **Output:** `ScopeResult`, a decision object with a status (`PASS`, `REVIEW`, `BLOCKED`) and a list of violations.

**Data Contracts:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ChangeContract:
    goal: str
    allowed_files: tuple[str, ...] = ()
    max_files: int = 10

@dataclass(frozen=True)
class ChangedFile:
    path: str
    changed_lines: int

@dataclass(frozen=True)
class ScopeResult:
    status: str # 'PASS', 'REVIEW', 'BLOCKED'
    violations: tuple[str, ...]
```

### 2. `SafetyActionGuard`

This guard acts as the final checkpoint before an agent performs a potentially destructive action.

*   **Purpose:** Prevents unsafe actions like file deletion, secret exfiltration, or arbitrary command execution.
*   **Input:** `ActionRequest`, a dataclass describing the proposed action (e.g., 'write', 'execute'), its target, and its risk profile.
*   **Output:** `SafetyResult`, a decision object with a status (`ALLOW`, `BLOCKED`).

**Data Contracts:**
```python
@dataclass(frozen=True)
class ActionRequest:
    action: str # 'read', 'write', 'execute_command'
    target: str
    is_destructive: bool = False

@dataclass(frozen=True)
class SafetyResult:
    status: str # 'ALLOW', 'BLOCKED'
    findings: tuple[str, ...]
```

### 3. `DebuggingLoopGuard`

This guard provides structure to the chaotic process of debugging, preventing an agent from getting stuck in repetitive, unproductive loops.

*   **Purpose:** Enforces a systematic, evidence-based debugging process.
*   **Input:** A `DebugAttempt` dataclass containing the hypothesis for a fix, and a history of previous `DebugAttempt`s.
*   **Output:** `DebugDecision`, which decides whether to `retain`, `revert`, `supersede`, or `escalate` the attempt. It critically blocks repeated, failed hypotheses.

### 4. `EvidenceLadderGuard` & `ProvenanceGuard`

These guards enforce the "Evidence-Driven" principle by classifying the quality and origin of evidence.

*   **Purpose:** Distinguishes between weak evidence (e.g., a mock) and strong evidence (e.g., a live user journey test).
*   **Concept:** The `ProvenanceGuard` labels all data with its origin (`Live`, `Mock`, `Synthetic`, `Cached`). The `EvidenceLadderGuard` ensures that a claim of success is supported by evidence of the required type and quality. It prevents an agent from claiming a feature is "verified" based only on synthetic data.

## Usage Example

Here's how you can use the guards in a simple Python script to validate a proposed change from an AI agent.

```python
from scopeguard import scope_guard, safety_guard

# 1. Define the contract for the task.
# The AI is only allowed to change 'app.py'.
contract = scope_guard.ChangeContract(
    goal="Add a new endpoint to the main app file.",
    allowed_files=("app.py",),
    max_files=1
)

# 2. Simulate the AI proposing its changes.
# The AI correctly changes app.py but also tries to modify a config file.
proposed_changes = (
    scope_guard.ChangedFile(path="app.py", changed_lines=15),
    scope_guard.ChangedFile(path="config.yaml", changed_lines=2) # This violates the contract.
)

# 3. Use ScopeGuard to evaluate the changes.
scope_result = scope_guard.evaluate(contract, proposed_changes)

print(f"Scope Guard Result: {scope_result.status}")
# Expected output: Scope Guard Result: REVIEW

if scope_result.status != 'PASS':
    print(f"Violations found: {scope_result.violations}")
    # Expected output: Violations found: ("File 'config.yaml' is not in the list of allowed files.",)

# 4. The AI now wants to write the file. Check if it's safe.
write_action = safety_guard.ActionRequest(action="write", target="app.py")
safety_result = safety_guard.authorize_action(write_action)

print(f"Safety Guard Result: {safety_result.status}")
# Expected output: Safety Guard Result: ALLOW
```

## Contributing

We welcome contributions! Please see our `CONTRIBUTING.md` for details on how to set up your development environment, run tests, and submit pull requests.

## License

ScopeGuard OS is licensed under the Apache 2.0 License.

---

### **Document 2: API Specifications for the `engine/` Backend**

# Scope Guard Platform API Specification v1.0

## Introduction

This document provides the official API specification for the Scope Guard Agent Platform backend. The frontend team ("Mission Control UI") should use this contract to build their components.

The API is a standard RESTful service with WebSocket support for real-time updates. All endpoints are prefixed with `/api`.

## Authentication

All API endpoints (except `/api/auth/token`) require authentication. The client must include a valid JSON Web Token (JWT) in the `Authorization` header.

`Authorization: Bearer <your_jwt_token>`

### **Auth Endpoint**

*   **Endpoint:** `POST /api/auth/token`
*   **Description:** Authenticates a user with a username and password and returns a JWT access token.
*   **Request Body:** `application/x-www-form-urlencoded`
    *   `username` (string, required)
    *   `password` (string, required)
*   **Success Response (200 OK):**
    ```json
    {
      "access_token": "ey...",
      "token_type": "bearer"
    }
    ```
*   **Error Response (401 Unauthorized):**
    ```json
    { "detail": "Incorrect username or password" }
    ```

## Endpoints

### Tasks

Tasks represent a single job for an agent, such as debugging an error or implementing a feature.

#### List All Tasks

*   **Endpoint:** `GET /api/tasks`
*   **Description:** Retrieves a summary of all tasks in the system. Intended for the main dashboard view.
*   **Authentication:** Required.
*   **Success Response (200 OK):**
    ```json
    [
      {
        "id": "c4a4a5a5-3a0c-4c7c-8e0a-4a7a7a7a7a7a",
        "status": "RUNNING",
        "source": "Sentry",
        "payload": {
          "type": "DEBUG_PRODUCTION_ERROR",
          "goal": "Fix production error: TypeError: 'NoneType' object is not callable"
        }
      }
    ]
    ```

#### Get Task Details

*   **Endpoint:** `GET /api/tasks/{task_id}`
*   **Description:** Retrieves the full details for a single task, including its complete log history.
*   **Authentication:** Required.
*   **Path Parameters:**
    *   `task_id` (string, required): The UUID of the task.
*   **Success Response (200 OK):**
    ```json
    {
      "id": "c4a4a5a5-3a0c-4c7c-8e0a-4a7a7a7a7a7a",
      "status": "AWAITING_PLAN_APPROVAL",
      "source": "Manual",
      "payload": {
        "type": "IMPLEMENT_FEATURE",
        "goal": "Add a CSV export button..."
      },
      "logs": [
        "Task created.",
        "Agent state: PLANNING_FEATURE",
        "AGENT: Awaiting user input for: ChangeContract(...)"
      ],
      "result": null
    }
    ```

#### Respond to Agent Prompt

*   **Endpoint:** `POST /api/tasks/{task_id}/respond`
*   **Description:** Allows the UI to submit a user's decision (e.g., 'approve' or 'deny') when an agent is in a waiting state.
*   **Authentication:** Required.
*   **Path Parameters:**
    *   `task_id` (string, required): The UUID of the task awaiting input.
*   **Request Body:** `application/json`
    ```json
    {
      "user_response": "yes"
    }
    ```
*   **Success Response (200 OK):**
    ```json
    { "status": "Response submitted" }
    ```

## WebSockets

### Live Log Stream

*   **Endpoint:** `WS /ws/tasks/{task_id}/logs`
*   **Description:** Provides a real-time stream of log messages for a specific running task. This is the primary mechanism for building a live-updating UI.
*   **Connection:** The client should establish a WebSocket connection to this endpoint. No authentication is specified for the WebSocket connection itself in v1, but the initial page load to get the `task_id` is authenticated.
*   **Messages:** The server will push plain text messages. Each message is a single log line from the agent's orchestrator.
    ```
    // Message 1 from server
    "Agent state: GENERATING_HYPOTHESIS"
    // Message 2 from server
    "Generated hypothesis: A function is being called on a None object..."
    // etc.
    ```
*   **Closing:** The connection will be closed by the server when the task enters a terminal state (`FINISHED` or `BLOCKED`).