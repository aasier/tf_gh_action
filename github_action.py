import requests
import time
import json
import argparse
import sys

GITHUB_API_URL = "https://api.github.com"

class GitHubActionRunner:
    def __init__(self, token, repo, workflow_id, branch="main", inputs=None):
        self.token = token
        self.repo = repo
        self.workflow_id = workflow_id
        self.branch = branch
        self.inputs = inputs or {}
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def trigger_workflow(self):
        """Triggers the GitHub Action workflow and returns True if successful."""
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/workflows/{self.workflow_id}/dispatches"
        payload = {"ref": self.branch}
        if self.inputs:
            payload["inputs"] = self.inputs

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code != 204:
            raise Exception(f"Failed to trigger workflow: {response.text}")

        print("✅ Workflow triggered successfully.")
        return True

    def get_latest_run(self):
        """Fetches the latest run of the workflow."""
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/runs"
       
        for _ in range(10):  # Retry logic
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch workflow runs: {response.text}")

            runs = response.json().get("workflow_runs", [])
            for run in runs:
                if run["name"] == self.workflow_id and run["head_branch"] == self.branch:
                    return run

            time.sleep(5)

        raise Exception("No recent workflow run found.")

    def wait_for_completion(self, run_id):
        """Waits for the workflow run to complete and returns the result."""
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/runs/{run_id}"
       
        while True:
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch run status: {response.text}")

            run_data = response.json()
            status = run_data["status"]
            conclusion = run_data.get("conclusion")
            logs_url = run_data["html_url"]
            duration = run_data.get("run_duration_ms", 0) / 1000  # Convert to seconds

            if status == "completed":
                return {
                    "status": status,
                    "conclusion": conclusion,
                    "logs_url": logs_url,
                    "duration_seconds": duration,
                    "outputs": run_data.get("outputs", {})  # Get outputs from workflow
                }

            time.sleep(10)

    def run(self):
        """Runs the full process: trigger, wait, and return the result."""
        self.trigger_workflow()
        time.sleep(5)  # Allow time for workflow to appear

        latest_run = self.get_latest_run()
        result = self.wait_for_completion(latest_run["id"])
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger a GitHub Action and get its result.")
    parser.add_argument("--token", required=True, help="GitHub API token")
    parser.add_argument("--repo", required=True, help="Repository in 'owner/repo' format")
    parser.add_argument("--workflow", required=True, help="Workflow ID or file name (e.g., deploy.yml)")
    parser.add_argument("--branch", default="main", help="Branch to trigger the workflow on")
    parser.add_argument("--inputs", type=json.loads, default="{}", help="JSON string of workflow inputs")

    args = parser.parse_args()

    try:
        runner = GitHubActionRunner(
            token=args.token,
            repo=args.repo,
            workflow_id=args.workflow,
            branch=args.branch,
            inputs=args.inputs
        )
        result = runner.run()
        print(json.dumps(result))  # Terraform can parse this output
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)