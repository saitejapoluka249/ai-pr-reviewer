import os
from typing import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver 
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Import tools from mcp_server.py
from mcp_server import get_pr_diff, run_pytest, post_github_comment, write_to_file, read_local_file, setup_workspace, push_fixed_code

load_dotenv()

# 1. Define the State
class AgentState(TypedDict):
    repo_name: str
    pr_number: int
    diff: str
    analysis: str
    test_results: str
    fix_attempts: int
    status: str 
    file_contents: str 

class ContextRequest(BaseModel):
    files_to_read: list[str] = Field(description="List of exact file paths to read. Always prefix with the repo folder name.")

# NEW: Model for a single file change
class SingleFileFix(BaseModel):
    file_path: str = Field(description="The exact relative path of the file to fix (including the repo folder prefix)")
    code: str = Field(description="The complete, fully fixed code to overwrite the file")

# NEW: Updated model to handle multiple file fixes in one response
class FixResponse(BaseModel):
    fixes: list[SingleFileFix] = Field(description="A list of one or more file fixes required to resolve the issues.")

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 2. Define the Nodes

def fetch_pr_node(state: AgentState):
    print("\n--- [NODE] PREPARING WORKSPACE & FETCHING PR ---")
    setup_status = setup_workspace(state['repo_name'], state['pr_number'])
    print(f"--- {setup_status} ---")
    
    diff = get_pr_diff(state['repo_name'], state['pr_number'])
    return {"diff": diff}

def analyze_code_node(state: AgentState):
    print("\n--- [NODE] ANALYZING CODE ---")
    prompt = f"Analyze this diff for bugs. If there's a bug, explain it. Diff:\n{state['diff']}"
    response = llm.invoke(prompt)
    return {"analysis": response.content}

def test_code_node(state: AgentState):
    print("\n--- [NODE] RUNNING TESTS ---")
    results = run_pytest(state['repo_name'])
    print(f"Test Output:\n{results}") 
    
    results_lower = results.lower()
    if "fail" in results_lower or "error" in results_lower or "exception" in results_lower:
        status = "FAIL"
    else:
        status = "PASS"
        
    return {"test_results": results, "status": status}

def gather_context_node(state: AgentState):
    print("\n--- [NODE] PRE-FIX INVESTIGATION (Reading Files) ---")
    repo_dir = state['repo_name'].split('/')[-1] 
    structured_llm = llm.with_structured_output(ContextRequest)
    
    prompt = f"""Tests failed:
{state['test_results']}

Initial PR Diff:
{state['diff']}

The code is located inside the directory: {repo_dir}/
Based on the error logs, what files do you need to read to understand ALL the bugs? Return their exact paths starting with {repo_dir}/"""

    response = structured_llm.invoke(prompt)
    
    contents = ""
    for path in response.files_to_read:
        print(f"--- AI is actively reading: {path} ---")
        contents += f"\n--- Contents of {path} ---\n{read_local_file(path)}\n"
        
    return {"file_contents": contents}

def fix_code_node(state: AgentState):
    print(f"\n--- [NODE] FIXING CODE (Attempt {state.get('fix_attempts', 0) + 1}) ---")
    repo_dir = state['repo_name'].split('/')[-1]
    structured_llm = llm.with_structured_output(FixResponse)
    
    # Updated prompt to encourage multi-file awareness
    prompt = f"""Tests failed:
{state['test_results']}

Here is the full context of the files you requested to read:
{state.get('file_contents', 'No additional files read.')}

The repository folder is: {repo_dir}/
Identify ALL files that contain bugs. Provide a list of fixes.
Each fix must include the exact file path (starting with {repo_dir}/) and the full, corrected code."""
    
    response = structured_llm.invoke(prompt)
    
    # NEW: Loop through all fixes provided by the AI
    for fix in response.fixes:
        print(f"--- AI is fixing: {fix.file_path} ---")
        write_to_file(fix.file_path, fix.code)
    
    return {"fix_attempts": state.get('fix_attempts', 0) + 1}

def comment_node(state: AgentState):
    print("\n--- [NODE] FINALIZING REVIEW & SYNCING ---")
    
    if state.get('fix_attempts', 0) > 0 and state['status'] == "PASS":
        print("--- Pushing fixed code to GitHub ---")
        push_status = push_fixed_code(state['repo_name'], state['pr_number'], "🤖 AI Auto-Fix: Resolved multiple failing tests")
        print(f"--- {push_status} ---")
        
        msg = f"✅ **AI Review: AUTONOMOUSLY FIXED & PUSHED**\n\n"
        msg += f"*Note: The initial code failed tests, but the AI applied fixes across multiple files and pushed them to the PR branch.*\n\n"
        msg += f"**Original Bug Analysis:**\n{state['analysis']}"
        
    elif state.get('fix_attempts', 0) > 0 and state['status'] == "FAIL":
        msg = f"❌ **AI Review: FAILED TO FIX**\n\n"
        msg += f"*Note: The AI attempted to fix the code {state['fix_attempts']} times, but tests are still failing. Human intervention required.*\n\n"
        msg += f"**Original Bug Analysis:**\n{state['analysis']}"
    else:
        msg = f"✅ **AI Review: {state['status']}**\n\n**Analysis:**\n{state['analysis']}"
        
    post_github_comment(state['repo_name'], state['pr_number'], msg)
    return {"status": "DONE"}

# 3. Build the Logic (The Workflow)

workflow = StateGraph(AgentState)

workflow.add_node("fetch_pr", fetch_pr_node)
workflow.add_node("analyze", analyze_code_node)
workflow.add_node("test", test_code_node)
workflow.add_node("gather_context", gather_context_node)
workflow.add_node("fix", fix_code_node)
workflow.add_node("comment", comment_node)

workflow.set_entry_point("fetch_pr")
workflow.add_edge("fetch_pr", "analyze")
workflow.add_edge("analyze", "test")

def route_after_test(state: AgentState):
    if state["status"] == "PASS" or state.get("fix_attempts", 0) >= 2:
        return "comment"
    return "gather_context"

workflow.add_conditional_edges("test", route_after_test, {"comment": "comment", "gather_context": "gather_context"})
workflow.add_edge("gather_context", "fix") 
workflow.add_edge("fix", "test")
workflow.add_edge("comment", END)

memory = MemorySaver()

app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["fix", "comment"]
)

# 4. Execution
if __name__ == "__main__":
    thread_config = {"configurable": {"thread_id": "multi-file-fix-run"}}
    
    inputs = {
        "repo_name": "saitejapoluka249/mcp-test-repo", 
        "pr_number": 2, # Update to the PR you want to test                               
        "fix_attempts": 0
    }
    
    print("Starting AI Reviewer...")
    
    for event in app.stream(inputs, config=thread_config):
        pass 
        
    snapshot = app.get_state(thread_config)
    next_steps = snapshot.next
    
    while next_steps:
        node_to_run = next_steps[0]
        print(f"\n⚠️  [HUMAN APPROVAL REQUIRED] ⚠️")
        user_input = input(f"The AI wants to proceed to '{node_to_run}'. Allow? (y/n): ")
        
        if user_input.strip().lower() == 'y':
            for event in app.stream(None, config=thread_config):
                pass
            snapshot = app.get_state(thread_config)
            next_steps = snapshot.next
        else:
            print("--- 🛑 Execution stopped. ---")
            break