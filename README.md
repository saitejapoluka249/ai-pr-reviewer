# 🤖 Autonomous GitHub PR Reviewer & Tester

An enterprise-grade **Agentic AI** system that automates the entire code review and testing lifecycle. Built with **LangGraph** and **Model Context Protocol (MCP)**, this agent doesn't just point out bugs—it dynamically clones repositories, investigates failures by reading source files, applies self-healing fixes across multiple files, and pushes the verified code back to GitHub.

---

## 🏛️ System Architecture

This system operates as a circular state machine, allowing for continuous feedback loops between testing and fixing.

### The "Brain" (LangGraph & LangChain)

The orchestration layer manages the **AgentState**, a short-term memory that tracks git diffs, real-time `pytest` logs, and fix attempts. It utilizes:

- **Structured Outputs**: Using Pydantic models to ensure the AI returns exact JSON data for multi-file fixes and context requests.
- **Human-in-the-Loop (HITL)**: Interactive checkpoints that pause execution for human approval before dangerous actions like writing code or posting public comments.

### The "Hands" (Model Context Protocol - MCP)

MCP acts as the bridge between the AI and the local system, providing specialized tools to:

- **Setup Workspace**: Dynamically clone any GitHub repository and checkout specific Pull Request branches.
- **Investigate**: Read full contents of local files to understand bug context.
- **Execute**: Trigger local test suites via `pytest`.
- **Sync**: Commit and push verified fixes directly back to the GitHub PR branch.

---

## 🌟 Key Features

- **Multi-File Self-Healing**: The agent can identify and fix bugs across multiple files in a single pass.
- **Repository Agnostic**: Automatically handles workspace preparation for any repository and PR number provided.
- **Closed-Loop Verification**: Fixes are only pushed if the local test suite passes.
- **Automated Cleanliness**: Dynamically manages `.gitignore` to prevent pushing temporary system files like `__pycache__`.

---

## 🚀 Workflow Breakdown

1. **Node: Fetch PR**: Dynamically clones the target repository and checks out the PR branch.
2. **Node: Analyze**: GPT-4o reasons about the PR diff to identify logical pitfalls.
3. **Node: Test**: Triggers a local `pytest` execution to verify code health.
4. **Node: Gather Context**: If tests fail, the AI autonomously decides which files to read to debug the failure.
5. **Node: Fix**: The agent generates code patches for one or more files and overwrites them locally.
6. **Node: Comment & Sync**: Summarizes the journey, posts a public review to GitHub, and pushes the fixed code if tests pass.

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
git clone https://github.com/saitejapoluka249/ai-pr-reviewer.git
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
   Update the `repo_name` and `pr_number` in `reviewer_agent.py` and run:

```bash
python3 reviewer_agent.py

```
