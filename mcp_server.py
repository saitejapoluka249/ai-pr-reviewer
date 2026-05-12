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

@mcp.tool()
def setup_workspace(repo_name: str, pr_number: int) -> str:
    """Dynamically clones the repository and checks out the specific PR branch."""
    repo_dir = repo_name.split("/")[-1]
    
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir, ignore_errors=True)
        
    token = os.getenv("GITHUB_TOKEN")
    clone_url = f"https://{token}@github.com/{repo_name}.git"
    
    try:
        subprocess.run(["git", "clone", clone_url, repo_dir], check=True, capture_output=True)
        
        # NEW FIX: Automatically create a .gitignore if it doesn't exist 
        # to prevent pushing __pycache__
        gitignore_content = "__pycache__/\n*.py[cod]\n.pytest_cache/\n.DS_Store\n"
        with open(os.path.join(repo_dir, ".gitignore"), "w") as f:
            f.write(gitignore_content)

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
    repo_dir = repo_name.split("/")[-1] 
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

# NEW TOOL: Automatically commit and push code back to GitHub
@mcp.tool()
def push_fixed_code(repo_name: str, pr_number: int, commit_message: str) -> str:
    """Commits and pushes local changes back to the original GitHub PR branch."""
    repo_dir = repo_name.split("/")[-1]
    try:
        # Get the actual branch name the PR was made from
        pr = gh.get_repo(repo_name).get_pull(pr_number)
        branch_name = pr.head.ref
        
        # Add files to git
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        
        # Check if there is anything to commit
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
        if not status.stdout.strip():
            return "No changes to commit."
            
        # Set a bot name for the commit
        subprocess.run(["git", "config", "user.name", "AI PR Reviewer Bot"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "ai-bot@example.com"], cwd=repo_dir, check=True)
        
        # Commit and push directly to the PR's remote branch
        subprocess.run(["git", "commit", "-m", commit_message], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", f"pr-{pr_number}:{branch_name}"], cwd=repo_dir, check=True, capture_output=True)
        
        return f"Success! Pushed commit to remote branch '{branch_name}'"
    except Exception as e:
        return f"Error pushing code: {str(e)}"

if __name__ == "__main__":
    mcp.run()