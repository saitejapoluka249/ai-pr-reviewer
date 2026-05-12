import os
from typing import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver 
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Import tools from mcp_server.py
from mcp_server import get_pr_diff, get_pr_filenames, run_pytest, post_github_comment, write_to_file, read_local_file, setup_workspace, push_fixed_code

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
    static_feedback: str 
    static_status: str

class ContextRequest(BaseModel):
    files_to_read: list[str] = Field(description="List of exact file paths to read. Always prefix with the repo folder name.")

class SingleFileFix(BaseModel):
    file_path: str = Field(description="The exact relative path of the file to fix (including the repo folder prefix)")
    code: str = Field(description="The complete, fully fixed code to overwrite the file")

class FixResponse(BaseModel):
    fixes: list[SingleFileFix] = Field(description="A list of one or more file fixes required to resolve the issues.")

class ReviewDecision(BaseModel):
    status: str = Field(description="Must be 'PASS' if the code is clean and bug-free, or 'FAIL' if there are bugs, bad practices, or style issues.")
    feedback: str = Field(description="Detailed explanation of the bugs found, style issues, or praise if passing.")

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 2. Define the Nodes

def fetch_pr_node(state: AgentState):
    print("\n--- [NODE] PREPARING WORKSPACE & FETCHING PR ---")
    setup_status = setup_workspace(state['repo_name'], state['pr_number'])
    print(f"--- {setup_status} ---")
    
    if "Error" in setup_status:
        raise RuntimeError(f"CRITICAL ERROR: Failed to prepare workspace. Agent stopped. Details: {setup_status}")
    
    diff = get_pr_diff(state['repo_name'], state['pr_number'])
    return {"diff": diff}

def analyze_code_node(state: AgentState):
    print("\n--- [NODE] ANALYZING DIFF ---")
    prompt = f"Analyze this diff for bugs. If there's a bug, explain it. Diff:\n{state['diff']}"
    response = llm.invoke(prompt)
    return {"analysis": response.content}

def read_direct_files_node(state: AgentState):
    print("\n--- [NODE] READING MODIFIED FILES ---")
    try:
        filenames = get_pr_filenames(state['repo_name'], state['pr_number'])
    except Exception as e:
        print(f"Failed to get filenames: {e}")
        filenames = []
    
    repo_dir = state['repo_name'].split('/')[-1]
    contents = "" 
    
    for f in filenames:
        full_path = f"{repo_dir}/{f}"
        print(f"--- Actively reading: {full_path} ---")
        contents += f"\n--- Contents of {full_path} ---\n{read_local_file(full_path)}\n"
        
    return {"file_contents": contents}

def static_review_node(state: AgentState):
    print("\n--- [NODE] AI STATIC CODE REVIEW ---")
    structured_llm = llm.with_structured_output(ReviewDecision)
    
    prompt = f"""You are an expert code reviewer.
    Review the CURRENT full contents of these files for any bugs, logical errors, or bad coding practices:
    
    === CURRENT FILE CONTENTS (Evaluate ONLY this code) ===
    {state.get('file_contents', 'No files read.')}
    =======================================================
    
    Do NOT grade based on past mistakes. Only look at the current file contents above.
    If the current code is clean and bug-free, return status 'PASS'.
    If there are bugs, return status 'FAIL' and provide detailed feedback."""
    
    response = structured_llm.invoke(prompt)
    print(f"Review Decision: {response.status}\nFeedback:\n{response.feedback}")
    
    return {"static_status": response.status, "static_feedback": response.feedback}

def test_code_node(state: AgentState):
    print("\n--- [NODE] RUNNING TESTS ---")
    results = run_pytest(state['repo_name'])
    print(f"Test Output:\n{results}") 
    
    results_lower = results.lower()
    if "fail" in results_lower or "error" in results_lower or "exception" in results_lower:
        test_status = "FAIL"
    else:
        test_status = "PASS"
        
    static_status = state.get('static_status', 'PASS')
    final_status = "FAIL" if (test_status == "FAIL" or static_status == "FAIL") else "PASS"
        
    return {"test_results": results, "status": final_status}

def gather_context_node(state: AgentState):
    print("\n--- [NODE] PRE-FIX INVESTIGATION (Reading Additional Files) ---")
    repo_dir = state['repo_name'].split('/')[-1] 
    structured_llm = llm.with_structured_output(ContextRequest)
    
    prompt = f"""Tests failed or code review failed:
Test logs: {state['test_results']}
Review feedback: {state.get('static_feedback', '')}

We already read the modified files. Based on the logs, do you need to read any OTHER files to understand ALL the bugs? Return their exact paths starting with {repo_dir}/"""

    response = structured_llm.invoke(prompt)
    
    contents = state.get('file_contents', '')
    for path in response.files_to_read:
        if path not in contents:
            print(f"--- AI is actively reading: {path} ---")
            contents += f"\n--- Contents of {path} ---\n{read_local_file(path)}\n"
        
    return {"file_contents": contents}

def fix_code_node(state: AgentState):
    print(f"\n--- [NODE] FIXING CODE (Attempt {state.get('fix_attempts', 0) + 1}) ---")
    repo_dir = state['repo_name'].split('/')[-1]
    structured_llm = llm.with_structured_output(FixResponse)
    
    prompt = f"""We need to fix the code. 

Test Results (Execution):
{state['test_results']}

Static Review Feedback (Style & Bugs):
{state.get('static_feedback', 'No static feedback.')}

Here is the full context of the files:
{state.get('file_contents', 'No additional files read.')}

Identify ALL files that contain bugs or style issues. Provide a list of fixes.
Each fix must include the exact file path (starting with {repo_dir}/) and the full, corrected code."""
    
    response = structured_llm.invoke(prompt)
    
    for fix in response.fixes:
        print(f"--- AI is fixing: {fix.file_path} ---")
        write_to_file(fix.file_path, fix.code)
    
    return {"fix_attempts": state.get('fix_attempts', 0) + 1}

# NEW NODE: Explicitly separated the push logic from the comment logic
def push_node(state: AgentState):
    print("\n--- [NODE] PUSHING FIXED CODE TO GITHUB ---")
    push_status = push_fixed_code(state['repo_name'], state['pr_number'], "🤖 AI Auto-Fix: Applied style/test fixes")
    print(f"--- {push_status} ---")
    return {}

def comment_node(state: AgentState):
    print("\n--- [NODE] POSTING FINAL COMMENT ---")
    
    if state.get('fix_attempts', 0) > 0 and state['status'] == "PASS":
        msg = f"✅ **AI Review: AUTONOMOUSLY CLEANED & PUSHED**\n\n"
        msg += f"*Note: The AI identified areas for improvement, applied fixes, verified tests, and pushed the updates.*\n\n"
        msg += f"**Original Analysis:**\n{state['analysis']}\n\n**Final Checks Passed!**"
        
    elif state.get('fix_attempts', 0) > 0 and state['status'] == "FAIL":
        msg = f"❌ **AI Review: FAILED TO FIX**\n\n"
        msg += f"*Note: The AI attempted to fix the code {state['fix_attempts']} times, but it is still failing checks. Human intervention required.*\n\n"
        msg += f"**Review Feedback:**\n{state.get('static_feedback', '')}\n\n**Test Logs:**\n{state['test_results'][:500]}..."
    else:
        msg = f"✅ **AI Review: PASS**\n\n**Analysis:**\n{state['analysis']}\n\nCode is clean and tests are passing!"
        
    post_github_comment(state['repo_name'], state['pr_number'], msg)
    return {"status": "DONE"}

# 3. Build the Logic (The Workflow)

workflow = StateGraph(AgentState)

workflow.add_node("fetch_pr", fetch_pr_node)
workflow.add_node("analyze", analyze_code_node)
workflow.add_node("read_files", read_direct_files_node)
workflow.add_node("static_review", static_review_node)
workflow.add_node("test", test_code_node)
workflow.add_node("gather_context", gather_context_node)
workflow.add_node("fix", fix_code_node)
workflow.add_node("push", push_node) # REGISTER NEW NODE
workflow.add_node("comment", comment_node)

workflow.set_entry_point("fetch_pr")
workflow.add_edge("fetch_pr", "analyze")
workflow.add_edge("analyze", "read_files")
workflow.add_edge("read_files", "static_review")
workflow.add_edge("static_review", "test")

def route_after_test(state: AgentState):
    # If code changed and it passes both static review & pytest -> Route to Push
    if state["status"] == "PASS" and state.get("fix_attempts", 0) > 0:
        return "push"
    # If code was perfectly fine to begin with OR it failed 2 attempts -> Route to Comment
    if state["status"] == "PASS" or state.get("fix_attempts", 0) >= 2:
        return "comment"
    # Otherwise -> Gather Context & Fix
    return "gather_context"

workflow.add_conditional_edges("test", route_after_test, {"push": "push", "comment": "comment", "gather_context": "gather_context"})
workflow.add_edge("gather_context", "fix") 
workflow.add_edge("fix", "read_files") 

# Ensure push connects to comment after finishing
workflow.add_edge("push", "comment")
workflow.add_edge("comment", END)

memory = MemorySaver()

app = workflow.compile(
    checkpointer=memory,
    # NOW SET TO INTERRUPT BEFORE BOTH PUSH AND COMMENT
    interrupt_before=["push", "comment"]
)

# 4. Execution
if __name__ == "__main__":
    thread_config = {"configurable": {"thread_id": "hybrid-review-run"}}
    
    inputs = {
        "repo_name": "saitejapoluka249/mcp-test-repo", 
        "pr_number": 2, # Ensure this is an Open PR number                               
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
            print("--- 🛑 Execution stopped by human. ---")
            break