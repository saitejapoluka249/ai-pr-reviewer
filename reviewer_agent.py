import os
from typing import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # NEW: For Human-in-the-loop memory
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

# Define the expected structured JSON output for fixes
class FixResponse(BaseModel):
    file_path: str = Field(description="The exact relative path of the file to fix (e.g., mcp-test-repo/calc.py)")
    code: str = Field(description="The complete, fully fixed code to overwrite the file")

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 2. Define the Nodes (The steps the AI takes)

def fetch_pr_node(state: AgentState):
    print("\n--- [NODE] FETCHING PR DIFF ---")
    diff = get_pr_diff(state['repo_name'], state['pr_number'])
    return {"diff": diff}

def analyze_code_node(state: AgentState):
    print("\n--- [NODE] ANALYZING CODE ---")
    prompt = f"Analyze this diff for bugs. If there's a bug, explain it. Diff:\n{state['diff']}"
    response = llm.invoke(prompt)
    return {"analysis": response.content}

def test_code_node(state: AgentState):
    print("\n--- [NODE] RUNNING TESTS ---")
    results = run_pytest()
    status = "FAIL" if "FAILED" in results else "PASS"
    return {"test_results": results, "status": status}

def fix_code_node(state: AgentState):
    print(f"\n--- [NODE] FIXING CODE (Attempt {state.get('fix_attempts', 0) + 1}) ---")
    
    structured_llm = llm.with_structured_output(FixResponse)
    
    prompt = f"""Tests failed:
{state['test_results']}

Based on the failed tests and the initial diff, identify which file needs to be fixed.
Provide the exact file path and the full, corrected code to overwrite it."""
    
    response = structured_llm.invoke(prompt)
    
    print(f"--- AI chose to fix: {response.file_path} ---")
    write_to_file(response.file_path, response.code)
    
    return {"fix_attempts": state.get('fix_attempts', 0) + 1}

def comment_node(state: AgentState):
    print("\n--- [NODE] POSTING COMMENT ---")
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

# NEW: Add a Checkpointer (Memory) to allow pausing the graph mid-execution
memory = MemorySaver()

# NEW: Compile the graph but tell it to PAUSE before running "fix" or "comment"
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["fix", "comment"]
)

# 4. Execution
if __name__ == "__main__":
    # A thread_id is required for memory to know which conversation/run this is
    thread_config = {"configurable": {"thread_id": "pr-review-run-1"}}
    
    inputs = {
        "repo_name": "saitejapoluka249/mcp-test-repo", 
        "pr_number": 2,                               
        "fix_attempts": 0
    }
    
    print("Starting AI Reviewer...")
    
    # Stream the graph until it hits a breakpoint
    for event in app.stream(inputs, config=thread_config):
        pass # The nodes themselves print their status
        
    # Check where the graph paused
    snapshot = app.get_state(thread_config)
    next_steps = snapshot.next
    
    # While there are still nodes waiting for approval
    while next_steps:
        node_to_run = next_steps[0]
        
        # Ask the human for permission
        print(f"\n⚠️  [HUMAN APPROVAL REQUIRED] ⚠️")
        user_input = input(f"The AI wants to proceed to the '{node_to_run}' step. Allow? (y/n): ")
        
        if user_input.strip().lower() == 'y':
            print(f"--- Proceeding with '{node_to_run}' ---")
            
            # Resume execution by passing None (it picks up exactly where it paused in memory)
            for event in app.stream(None, config=thread_config):
                pass
            
            # Check the state again to see if it paused at a new node 
            # (e.g., it ran 'fix', then 'test', and is now paused at 'comment')
            snapshot = app.get_state(thread_config)
            next_steps = snapshot.next
        else:
            print("--- 🛑 Execution stopped by human. ---")
            break