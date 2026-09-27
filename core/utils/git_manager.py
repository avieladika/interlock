import os
import subprocess
import shutil
import time

class GitManager:
    def __init__(self, repo_url: str, local_path: str):
        self.repo_url = repo_url
        self.local_path = os.path.abspath(local_path) # Use absolute path

    def ensure_repo(self):
        """
        Clones the repo if it doesn't exist, or fetches updates if it does.
        """
        git_dir = os.path.join(self.local_path, ".git")
        
        if os.path.exists(git_dir):
            print(f"🔄 Repo exists at {self.local_path}. Fetching updates...")
            self._run_git(["fetch", "--all"])
        else:
            print(f"📥 Cloning repo from {self.repo_url} to {self.local_path}...")
            
            # Clean up if directory exists but is not a valid git repo
            if os.path.exists(self.local_path):
                print(f"   ⚠️ Directory exists but is not a git repo. Deleting: {self.local_path}")
                try:
                    shutil.rmtree(self.local_path)
                    # Wait a bit for FS to catch up
                    time.sleep(0.5)
                except Exception as e:
                    print(f"   ❌ Failed to delete directory: {e}")
                    # If delete fails, git clone will likely fail too
            
            # Ensure parent dir exists
            os.makedirs(os.path.dirname(self.local_path), exist_ok=True)
            
            # Clone
            self._run_git(["clone", self.repo_url, self.local_path], cwd=os.path.dirname(self.local_path))

    def checkout_branch(self, branch_name: str):
        """
        Checks out the specified branch.
        """
        print(f"🔀 Checking out branch: {branch_name}...")
        try:
            self._run_git(["checkout", branch_name])
            self._run_git(["pull", "origin", branch_name]) # Ensure it's up to date
        except Exception as e:
            print(f"⚠️ Failed to checkout {branch_name}: {e}")

    def _run_git(self, args: list, cwd: str = None):
        cwd = cwd or self.local_path
        
        # If cwd doesn't exist (e.g. before clone), use parent or current dir
        if not os.path.exists(cwd):
            cwd = os.getcwd()

        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {' '.join(args)}\nError: {e.stderr}") from e
