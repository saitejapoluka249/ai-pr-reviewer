import os
import subprocess
import shutil
from mcp.server.fastmcp import FastMCP
from github import Github, Auth
from dotenv import load_dotenv

# Load credentials
load_dotenv()
auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
gh = Github(auth=auth)

# Initialize FastMCP Server
mcp = FastMCP("PR_Review_Helper")

# NEW TOOL: Dynamically prepares any repo and PR for testing
@mcp.tool()
def setup_workspace(repo_name: str, pr_number: int) -> str:
    """Dynamically clones the repository and checks out the specific PR branch."""
    repo_dir = repo_name.split("/")[-1]
    
    # Clean up existing folder to ensure a fresh test environment
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir, ignore_errors=True)
        
    # Use token to securely clone (works for private repos too)
    token = os.getenv("GITHUB_TOKEN")
    clone_url = f"https://{token}@github.com/{repo_name}.git"
    
    try:
        # 1. Clone the base repo
        subprocess.run(["git", "clone", clone_url, repo_dir], check=True, capture_output=True)
        
        # 2. Fetch the specific PR branch and check it out
        subprocess.run(["git", "fetch", "origin", f"pull/{pr_number}/head:pr-{pr_number}"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", f"pr-{pr_number}"], cwd=repo_dir, check=True, capture_output=True)
        
        return f"Workspace Setup Success: Cloned {repo_name} and checked out PR #{pr_number}"
    except Exception as e:
        return f"Error setting up workspace: {str(e)}"

@mcp.tool()
def get_pr_diff(repo_name: str, pr_number: int) -> str:
    """Fetches the git diff of a specific Pull Request."""
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    files = pr.get_files()
    diff_content = ""
    for file in files:
        diff_content += f"File: {file.filename}\nPatch:\n{file.patch}\n\n"
    
    return diff_content

@mcp.tool()
def run_pytest(repo_name: str) -> str:
    """Runs pytest dynamically in the specified repository folder."""
    repo_dir = repo_name.split("/")[-1] # Dynamically get the folder name
    try:
        result = subprocess.run(
            ["pytest", repo_dir, "--maxfail=5", "--disable-warnings"],
            capture_output=True,
            text=True
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error running tests: {str(e)}"

@mcp.tool()
def post_github_comment(repo_name: str, pr_number: int, comment: str):
    """Posts a comment on the specified GitHub Pull Request."""
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(comment)
    return "Comment posted successfully."

@mcp.tool()
def write_to_file(file_path: str, content: str) -> str:
    """Overwrites a local file with new content. Use this to apply fixes."""
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return f"Successfully updated {file_path}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"

@mcp.tool()
def read_local_file(file_path: str) -> str:
    """Reads the full content of a local file."""
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

if __name__ == "__main__":
    mcp.run()