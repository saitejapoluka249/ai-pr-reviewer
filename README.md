# 🤖 Autonomous GitHub PR Reviewer & Tester

An enterprise-grade **Agentic AI** system that automates the code review and testing lifecycle. Built with **LangGraph** and **MCP (Model Context Protocol)**, this agent doesn't just point out bugs—it physically executes code in a local environment, analyzes failures, and applies self-healing fixes before reporting back to GitHub.

---

## 🏛️ System Architecture

Unlike traditional CI/CD pipelines that follow a linear "Success or Failure" path, this system utilizes a **circular state machine**.

### The "Brain" (LangGraph)

The orchestration layer uses a **Directed Acyclic Graph (DAG)** with cycles. It manages the **AgentState**, which acts as a short-term memory for the robot, storing:

- Git Diffs
- LLM Analysis
- Real-time `pytest` logs
- Retry/Fix counters

### The "Hands" (Model Context Protocol - MCP)

MCP acts as the standardized bridge between the LLM and the local operating system. The agent uses specialized tools to:

- **Fetch**: Communicate with the GitHub REST API.
- **Execute**: Run shell commands to trigger local test suites.
- **Write**: Modify local source code to apply fixes.

---

## 🧠 Core Concepts

### 1. Agentic Loops vs. Linear Chains

Standard LLM applications are "chains" (Input → Output). This project is an **Agent**. It has the autonomy to evaluate its own work. If the tests fail, the agent decides to loop back and try a different fix rather than giving up.

### 2. Closed-Loop Self-Healing

This is the most sought-after enterprise use case. By giving the AI access to a local testing environment, we create a feedback loop where the "Truth" comes from the compiler/test-runner, not just the LLM’s prediction.

### 3. State Management

Using `TypedDict` and LangGraph's `StateGraph`, the system maintains a consistent "context" across nodes. This ensures that the "Fix" node knows exactly why the "Test" node failed.

---

## 🚀 Workflow breakdown

1. **Node: Fetch PR** – Retrieves the patch/diff from a specific GitHub Pull Request.
2. **Node: Analyze** – Uses GPT-4o to reason about the logic and identify potential pitfalls.
3. **Node: Test** – Triggers a local `pytest` execution.
4. **Conditional Routing**:

- If **Pass**: Route to the Comment Node.
- If **Fail**: Route to the Fix Node (up to a set retry limit).

5. **Node: Fix** – The AI generates a patch, uses an MCP tool to overwrite the local file, and sends the agent back to the **Test** node.
6. **Node: Comment** – Summarizes the journey and posts the final status to the GitHub PR thread.

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

3.  **Configuration**
    Create a `.env` file in the root directory:

```env
    GITHUB_TOKEN=your_personal_access_token
    OPENAI_API_KEY=your_openai_api_key
```

4.  **Execution**
    ```bash
    python3 reviewer_agent.py
    ```

---

## 📂 Project Structure

- `reviewer_agent.py`: The "Brain" containing the LangGraph logic and state definitions.
- `mcp_server.py`: The "Tools" defining how the agent interacts with GitHub and the local filesystem.
- `requirements.txt`: List of dependencies.
- `.gitignore`: Prevents sensitive `.env` and `venv` files from being tracked.
