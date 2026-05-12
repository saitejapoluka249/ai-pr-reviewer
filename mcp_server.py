import os
import subprocess
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
def run_pytest() -> str:
    """Runs pytest in the local environment and returns the output."""
    try:
        # We run pytest inside the mcp-test-repo folder
        result = subprocess.run(
            ["pytest", "mcp-test-repo", "--maxfail=5", "--disable-warnings"],
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

if __name__ == "__main__":
    mcp.run()