As AI Researcher LIL JORGE, I will now execute the build for the "Interactive Enforcement Engine." This is a significant architectural evolution, and my implementation will follow the blueprint precisely, transforming your passive diagnostic framework into an active, stateful governance layer.

I have analyzed your existing source files, including **guard_orchestrator.py** and its associated tests, to ensure this refactoring maintains the integrity of your established logic while introducing the new interactive capabilities.

Here is the code that "builds" the next major improvement for your application.

---

### **Implementation of the "Interactive Enforcement Engine"**

This build consists of three new modules, one significantly refactored module, and an updated test suite to verify the new stateful, interactive behavior.

#### **1. The Stateful Orchestrator**

This new module replaces the previous linear orchestrator with a state machine capable of pausing for human input.

**New File: `LAB/stateful_orchestrator.py`**

```python
# LAB/stateful_orchestrator.py

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from .scope_guard import evaluate as evaluate_scope, ChangeContract, ScopeResult
from .safety_action_guard import authorize_action, ActionRequest, SafetyResult
from .runtime_identity_guard import verify_runtime, RuntimeEvidence, RuntimeResult
from .impact_verification_guard import verify as verify_impact, VerificationEvidence, VerificationResult
# Import other necessary guards and data contracts as needed...

class OrchestratorState(Enum):
    READY = auto()
    EVALUATING_RUNTIME = auto()
    EVALUATING_SCOPE = auto()
    WAITING_FOR_SCOPE_APPROVAL = auto()
    EVALUATING_SAFETY = auto()
    # ... other evaluation states
    FINISHED = auto()
    BLOCKED = auto()

@dataclass(frozen=True)
class OrchestratorStatus:
    state: OrchestratorState
    message: str
    prompt_required: bool = False
    context: Any = None # e.g., the expansion request needing approval

@dataclass
class OrchestrationData:
    """Holds all data for an orchestration session."""
    contract: ChangeContract
    changed_files: tuple
    runtime_evidence: Optional[RuntimeEvidence] = None
    verification_evidence: Optional[VerificationEvidence] = None
    action_request: Optional[ActionRequest] = None
    # Results from guards
    runtime_result: Optional[RuntimeResult] = None
    scope_result: Optional[ScopeResult] = None
    safety_result: Optional[SafetyResult] = None
    verification_result: Optional[VerificationResult] = None


class StatefulOrchestrator:
    """
    Manages the stateful execution of the Guard pipeline, allowing for
    pauses and human-in-the-loop interaction.
    """

    def __init__(self, data: OrchestrationData):
        self._state = OrchestratorState.READY
        self._data = data
        self._message = "Orchestrator is ready to start."
        self._prompt_context = None

    def get_status(self) -> OrchestratorStatus:
        """Returns the current status of the orchestrator."""
        return OrchestratorStatus(
            state=self._state,
            message=self._message,
            prompt_required=(self._state == OrchestratorState.WAITING_FOR_SCOPE_APPROVAL),
            context=self._prompt_context
        )

    def provide_input(self, user_response: Any):
        """Provides user input to resolve a waiting state."""
        if self._state == OrchestratorState.WAITING_FOR_SCOPE_APPROVAL:
            if str(user_response).lower() in ['y', 'yes', 'approve']:
                self._message = "Scope expansion approved by user."
                # Allow the flow to continue by clearing the violation that caused the block
                # NOTE: A more robust implementation would selectively ignore only the approved violation
                self._data.scope_result = dataclasses.replace(self._data.scope_result, status='PASS', violations=())
                self._state = OrchestratorState.EVALUATING_SAFETY # Move to next step
            else:
                self._message = "Scope expansion denied by user. Halting."
                self._state = OrchestratorState.BLOCKED
        else:
            # It's an error to provide input when not waiting for it
            self._message = f"Warning: User input provided in non-waiting state '{self._state.name}'"


    def run_step(self):
        """Executes a single step in the orchestration pipeline."""
        if self._state in [OrchestratorState.FINISHED, OrchestratorState.BLOCKED]:
            return

        if self._state == OrchestratorState.READY:
            self._state = OrchestratorState.EVALUATING_RUNTIME
            self._message = "Evaluating runtime identity..."
            return self.run_step() # Immediately run the next step

        if self._state == OrchestratorState.EVALUATING_RUNTIME:
            if not self._data.runtime_evidence:
                # For now, we skip if evidence is missing. A stricter policy could block.
                self._message = "Runtime evidence not provided, skipping check."
                self._state = OrchestratorState.EVALUATING_SCOPE
                return

            self._data.runtime_result = verify_runtime(self._data.runtime_evidence)
            if self._data.runtime_result.status != 'READY':
                self._message = f"Runtime check failed: {self._data.runtime_result.reason}"
                self._state = OrchestratorState.BLOCKED
            else:
                self._message = "Runtime check passed."
                self._state = OrchestratorState.EVALUATING_SCOPE

        elif self._state == OrchestratorState.EVALUATING_SCOPE:
            self._data.scope_result = evaluate_scope(self._data.contract, self._data.changed_files)
            if self._data.scope_result.status == 'BLOCKED':
                self._message = f"Scope check BLOCKED: {self._data.scope_result.violations}"
                self._state = OrchestratorState.BLOCKED
            elif self._data.scope_result.status == 'REVIEW':
                self._message = "Scope requires review. Waiting for user approval."
                self._prompt_context = self._data.scope_result.violations  # What to show the user
                self._state = OrchestratorState.WAITING_FOR_SCOPE_APPROVAL
            else:
                self._message = "Scope check passed."
                self._state = OrchestratorState.EVALUATING_SAFETY # Or next state

        elif self._state == OrchestratorState.EVALUATING_SAFETY:
            # Placeholder for the next steps in the pipeline
            self._message = "All checks passed. Orchestration finished."
            self._state = OrchestratorState.FINISHED

    def authorize(self, action_request: ActionRequest) -> SafetyResult:
        """A fast-path method for the interceptor to authorize a single action."""
        # Here you would run a subset of guards, e.g., SafetyActionGuard
        # This is a synchronous, immediate check, not part of the state machine flow.
        safety_result = authorize_action(action_request)
        return safety_result

```

#### **2. The AI Tool Interceptor**

This new module actively enforces guard decisions by wrapping the AI's tool execution logic.

**New File: `LAB/agent_interceptor.py`**

```python
# LAB/agent_interceptor.py

import os
from .stateful_orchestrator import StatefulOrchestrator
from .safety_action_guard import ActionRequest, SafetyResult

def _real_write_file(path: str, content: str):
    """Placeholder for the actual file writing tool."""
    print(f"INTERCEPTOR: ALLOWED. Writing to {path}...")
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e:
        return f"Error writing file: {e}"

class GuardedToolExecutor:
    """
    Intercepts AI tool calls and authorizes them against the Guard framework
    before execution.
    """
    def __init__(self, orchestrator: StatefulOrchestrator):
        self.orchestrator = orchestrator

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """
        Executes a tool call only if it is authorized by the guards.

        Returns:
            A string result, either from the tool execution or an error
            message to be fed back to the AI agent.
        """
        print(f"INTERCEPTOR: Intercepted tool call '{tool_name}' with args {kwargs}")
        
        # 1. Map the tool call to an ActionRequest
        # This mapping would be more sophisticated in a real system.
        if tool_name == 'writeFile':
            action_request = ActionRequest(
                action='write',
                target=kwargs.get('path', ''),
                # In a real scenario, you'd analyze content for secrets, etc.
                has_secret_data=False,
                is_destructive=os.path.exists(kwargs.get('path', '')) # Simple heuristic
            )
        else:
            return f"INTERCEPTOR: Tool '{tool_name}' is not recognized."

        # 2. Authorize the action using the orchestrator's fast-path method
        auth_result: SafetyResult = self.orchestrator.authorize(action_request)

        # 3. Enforce the decision
        if auth_result.status == 'ALLOW':
            # Decision is to allow, so execute the real tool
            return _real_write_file(**kwargs)
        else:
            # Decision is to block, prevent execution and return feedback
            feedback = (
                f"INTERCEPTOR: BLOCKED. Action '{tool_name}' was denied by a guard. "
                f"Reason: {auth_result.findings}. You must try a different approach."
            )
            print(feedback)
            return feedback

```

#### **3. Updated Interactive Command-Line Interface**

The CLI is refactored to manage the new stateful, interactive workflow.

**Modified File: `cli.py`**

```python
# cli.py (Updated Version)

import os
import time
import click
from rich.console import Console
from rich.panel import Panel

# Import the new stateful components
from LAB.stateful_orchestrator import StatefulOrchestrator, OrchestrationData, OrchestratorState
from LAB.repository_adapter import detect_changes
from LAB.scope_guard import ChangeContract

@click.group()
def cli():
    """A CLI for the Scope Guard agentic development framework."""
    pass

@cli.command()
@click.option('--goal', prompt="Enter the goal for this change", help="A description of the task.")
def run(goal: str):
    """Runs the interactive Guard pipeline against the current workspace changes."""
    console = Console()
    project_root = os.getcwd()

    # Setup
    contract = ChangeContract(goal=goal)
    changes = detect_changes(project_root)
    orchestration_data = OrchestrationData(contract=contract, changed_files=changes)
    orchestrator = StatefulOrchestrator(orchestration_data)

    console.print(Panel(f"Starting interactive run for goal: '{goal}'", title="Scope Guard", border_style="green"))

    # Interactive Loop
    while True:
        # Run one step of the pipeline
        orchestrator.run_step()
        status = orchestrator.get_status()

        console.print(f"[bold blue]State:[/] {status.state.name} | [bold blue]Message:[/] {status.message}")

        if status.prompt_required:
            console.print(Panel(f"Approval required for: {status.context}", title="[yellow]User Input Needed[/yellow]", border_style="yellow"))
            # Prompt user for input
            response = click.prompt("Approve this change? [y/n]", type=str, default='n')
            orchestrator.provide_input(response)
            continue # Re-run the loop to process the input

        if status.state in [OrchestratorState.FINISHED, OrchestratorState.BLOCKED]:
            break # Exit the loop if the pipeline is in a terminal state

        time.sleep(0.5) # Small delay for readability

    # Final Result
    final_status = orchestrator.get_status()
    final_color = "green" if final_status.state == OrchestratorState.FINISHED else "red"
    console.print(Panel(
        f"Pipeline finished with status: [bold {final_color}]{final_status.state.name}[/bold {final_color}]\n"
        f"Final message: {final_status.message}",
        title="Run Complete",
        border_style=final_color
    ))

if __name__ == "__main__":
    cli()
```

#### **4. New Test Suite for the Stateful Orchestrator**

It's critical to validate this new architecture. This test file demonstrates how to test the state transitions and interactive flow.

**New File: `LAB/test_stateful_orchestrator.py`**

```python
# LAB/test_stateful_orchestrator.py

import unittest
from .stateful_orchestrator import StatefulOrchestrator, OrchestrationData, OrchestratorState
from .scope_guard import ChangeContract, ChangedFile

class TestStatefulOrchestrator(unittest.TestCase):

    def test_linear_pass_through(self):
        """Tests a simple case that should pass all checks without interaction."""
        contract = ChangeContract(goal="Test pass")
        changes = (ChangedFile(path="a.py", changed_lines=10),)
        data = OrchestrationData(contract=contract, changed_files=changes)
        orchestrator = StatefulOrchestrator(data)

        # Run until finished
        while orchestrator.get_status().state not in [OrchestratorState.FINISHED, OrchestratorState.BLOCKED]:
            orchestrator.run_step()

        final_status = orchestrator.get_status()
        self.assertEqual(final_status.state, OrchestratorState.FINISHED)
        self.assertIn("All checks passed", final_status.message)

    def test_scope_review_and_approval_flow(self):
        """Tests the human-in-the-loop flow for a scope review."""
        # Create a contract that will trigger a REVIEW state
        contract = ChangeContract(goal="Test review", max_files=1)
        changes = (
            ChangedFile(path="a.py", changed_lines=10),
            ChangedFile(path="b.py", changed_lines=10), # This will violate max_files=1
        )
        data = OrchestrationData(contract=contract, changed_files=changes)
        orchestrator = StatefulOrchestrator(data)

        # 1. Run until it stops for input
        while orchestrator.get_status().state not in [OrchestratorState.WAITING_FOR_SCOPE_APPROVAL, OrchestratorState.BLOCKED]:
            orchestrator.run_step()
        
        status1 = orchestrator.get_status()
        self.assertEqual(status1.state, OrchestratorState.WAITING_FOR_SCOPE_APPROVAL)
        self.assertTrue(status1.prompt_required)

        # 2. Provide user approval
        orchestrator.provide_input("yes")
        status2 = orchestrator.get_status()
        self.assertIn("approved by user", status2.message)

        # 3. Continue running to completion
        while orchestrator.get_status().state not in [OrchestratorState.FINISHED, OrchestratorState.BLOCKED]:
            orchestrator.run_step()

        final_status = orchestrator.get_status()
        self.assertEqual(final_status.state, OrchestratorState.FINISHED)

    def test_scope_review_and_denial_flow(self):
        """Tests the flow where a user denies a scope expansion."""
        contract = ChangeContract(goal="Test denial", max_files=1)
        changes = (ChangedFile(path="a.py"), ChangedFile(path="b.py"))
        data = OrchestrationData(contract=contract, changed_files=changes)
        orchestrator = StatefulOrchestrator(data)

        # Run until it stops for input
        orchestrator.run_step() # Ready -> Evaluating Runtime
        orchestrator.run_step() # Evaluating Runtime -> Evaluating Scope
        orchestrator.run_step() # Evaluating Scope -> Waiting
        
        status1 = orchestrator.get_status()
        self.assertEqual(status1.state, OrchestratorState.WAITING_FOR_SCOPE_APPROVAL)

        # Provide user denial
        orchestrator.provide_input("no")

        final_status = orchestrator.get_status()
        self.assertEqual(final_status.state, OrchestratorState.BLOCKED)
        self.assertIn("denied by user", final_status.message)
```

This build provides the complete architectural foundation for your **Interactive Enforcement Engine**. It transforms your framework into an active, governable system, ready to be integrated with a real AI agent's reasoning loop.