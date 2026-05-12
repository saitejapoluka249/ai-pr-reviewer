import os
from typing import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Import the tools we wrote in the other file
from mcp_server import get_pr_diff, run_pytest, post_github_comment, write_to_file

load_dotenv()

# 1. Define the State (The data that moves through the graph)
class AgentState(TypedDict):
    repo_name: str
    pr_number: int
    diff: str
    analysis: str
    test_results: str
    fix_attempts: int
    status: str # "PASS", "FAIL"

# NEW: Define the expected structured JSON output for fixes
class FixResponse(BaseModel):
    file_path: str = Field(description="The exact relative path of the file to fix (e.g., mcp-test-repo/calc.py)")
    code: str = Field(description="The complete, fully fixed code to overwrite the file")

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 2. Define the Nodes (The steps the AI takes)

def fetch_pr_node(state: AgentState):
    print("--- [NODE] FETCHING PR DIFF ---")
    diff = get_pr_diff(state['repo_name'], state['pr_number'])
    return {"diff": diff}

def analyze_code_node(state: AgentState):
    print("--- [NODE] ANALYZING CODE ---")
    prompt = f"Analyze this diff for bugs. If there's a bug, explain it. Diff:\n{state['diff']}"
    response = llm.invoke(prompt)
    return {"analysis": response.content}

def test_code_node(state: AgentState):
    print("--- [NODE] RUNNING TESTS ---")
    results = run_pytest()
    status = "FAIL" if "FAILED" in results else "PASS"
    return {"test_results": results, "status": status}

def fix_code_node(state: AgentState):
    print(f"--- [NODE] FIXING CODE (Attempt {state.get('fix_attempts', 0) + 1}) ---")
    
    # NEW: Bind the LLM to the Pydantic model to guarantee a structured JSON response
    structured_llm = llm.with_structured_output(FixResponse)
    
    prompt = f"""Tests failed:
{state['test_results']}

Based on the failed tests and the initial diff, identify which file needs to be fixed.
Provide the exact file path and the full, corrected code to overwrite it."""
    
    # Invoke now returns a validated FixResponse object instead of a raw text string
    response = structured_llm.invoke(prompt)
    
    # Dynamically pass the AI-selected file path to the MCP tool
    print(f"--- AI chose to fix: {response.file_path} ---")
    write_to_file(response.file_path, response.code)
    
    return {"fix_attempts": state.get('fix_attempts', 0) + 1}

def comment_node(state: AgentState):
    print("--- [NODE] POSTING COMMENT ---")
    msg = f"AI Review: {state['status']}\n\nAnalysis: {state['analysis']}"
    post_github_comment(state['repo_name'], state['pr_number'], msg)
    return {"status": "DONE"}

# 3. Build the Logic (The Workflow)

workflow = StateGraph(AgentState)

workflow.add_node("fetch_pr", fetch_pr_node)
workflow.add_node("analyze", analyze_code_node)
workflow.add_node("test", test_code_node)
workflow.add_node("fix", fix_code_node)
workflow.add_node("comment", comment_node)

workflow.set_entry_point("fetch_pr")
workflow.add_edge("fetch_pr", "analyze")
workflow.add_edge("analyze", "test")

# The Router: decide if we fix or comment
def route_after_test(state: AgentState):
    if state["status"] == "PASS" or state.get("fix_attempts", 0) >= 2:
        return "comment"
    return "fix"

workflow.add_conditional_edges("test", route_after_test, {"comment": "comment", "fix": "fix"})
workflow.add_edge("fix", "test")
workflow.add_edge("comment", END)

app = workflow.compile()

# 4. Execution
if __name__ == "__main__":
    inputs = {
        "repo_name": "saitejapoluka249/mcp-test-repo", 
        "pr_number": 2,                               
        "fix_attempts": 0
    }
    app.invoke(inputs)