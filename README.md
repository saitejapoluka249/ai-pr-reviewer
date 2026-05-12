# 🤖 Autonomous GitHub PR Reviewer & Tester (Hybrid Agent)

An enterprise-grade **Agentic AI** system that automates the entire code review and testing lifecycle. Built with **LangGraph** and **Model Context Protocol (MCP)**, this agent acts as both a Senior Code Reviewer and an Automated QA Tester.

It dynamically clones repositories, reads source code to enforce style and logic, triggers local test suites, applies self-healing fixes across multiple files, and pushes the verified code back to GitHub.

---

## 🏛️ System Architecture: The Hybrid Approach

This system operates as a circular state machine using a **Hybrid Review Architecture** (Static Analysis + Dynamic Execution).

### The "Brain" (LangGraph & LangChain)

The orchestration layer manages the **AgentState**, a short-term memory that tracks git diffs, file contents, real-time `pytest` logs, and static review feedback. It utilizes:

- **Structured Outputs**: Using Pydantic models to ensure the AI returns exact JSON data for multi-file fixes and context requests.
- **Cyclical Self-Healing**: The graph loops through fixing and testing until both the static review and dynamic tests pass.
- **Human-in-the-Loop (HITL)**: Interactive checkpoints that pause execution for human approval before dangerous actions like posting public comments or pushing code.

### The "Hands" (Model Context Protocol - MCP)

MCP acts as the bridge between the AI and the local system, providing specialized tools to:

- **Setup Workspace**: Dynamically clone any GitHub repository and checkout specific Pull Request branches.
- **Investigate**: Read full contents of local files to understand bug context and style.
- **Execute**: Trigger local test suites via `pytest`.
- **Sync**: Commit and push verified fixes directly back to the GitHub PR branch.

---

## 🌟 Key Features

- **Hybrid AI Review**: Combines Static Code Review (checking for bad variable names, missing comments, logic flaws) with Dynamic Testing (running `pytest`).
- **Multi-File Self-Healing**: The agent can identify and fix bugs across multiple files in a single pass.
- **Repository Agnostic**: Automatically handles workspace preparation for any repository and PR number provided.
- **Closed-Loop Verification**: Code is only pushed back to GitHub if it passes _both_ the AI's strict static review and the local test suite.
- **Automated Cleanliness**: Dynamically manages `.gitignore` to prevent pushing temporary system files like `__pycache__`.

---

## 🚀 Workflow Breakdown

1. **Fetch PR**: Dynamically clones the target repository and checks out the PR branch.
2. **Analyze Diff**: GPT-4o reasons about the initial PR diff to identify logical pitfalls.
3. **Read Modified Files**: Ingests the full contents of the files touched in the PR.
4. **Static Review**: The AI acts as a Senior Developer, grading the code for bugs, logic, and stylistic best practices.
5. **Dynamic Test**: Triggers a local `pytest` execution to verify code health mathematically.
6. **Gather Context (Conditional)**: If tests fail, the AI autonomously decides which _additional_ files to read to debug the failure.
7. **Fix Code (Conditional)**: The agent generates code patches and overwrites the files locally to fix any test failures or static review feedback. Loops back to Step 3.
8. **Comment & Sync**: Summarizes the journey, posts a public review to GitHub, and automatically commits and pushes the fixed code.

---

## 🛠️ Tech Stack

- **Orchestration**: [LangGraph](https://github.com/langchain-ai/langgraph)
- **LLM Framework**: [LangChain](https://github.com/langchain-ai/langchain)
- **Model**: OpenAI GPT-4o
- **Interface**: Model Context Protocol (MCP)
- **Version Control**: PyGithub (GitHub API)
- **Testing**: Pytest

---

## 📦 Installation & Setup

1. **Clone the Repository**

```bash
git clone [https://github.com/saitejapoluka249/ai-pr-reviewer.git](https://github.com/saitejapoluka249/ai-pr-reviewer.git)
cd ai-pr-reviewer

```

2. **Environment Setup**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

```

3. **Configuration**
   Create a `.env` file in the root directory:

```env
GITHUB_TOKEN=your_personal_access_token
OPENAI_API_KEY=your_openai_api_key

```

4. **Execution**
   Update the `repo_name` and `pr_number` at the bottom of `reviewer_agent.py` and run:

```bash
python3 reviewer_agent.py

```
