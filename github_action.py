import requests
import time
import json
import argparse
import sys
import logging
from logging.handlers import RotatingFileHandler

# Configurar logging (archivo + terminal)
log_file = "github_action.log"

# Configurar rotación de logs (1MB máx, 5 archivos)
file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

# Configurar salida en terminal
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(message)s"))

# Configurar logging global
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

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
        """Triggers the GitHub Action workflow."""
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/workflows/{self.workflow_id}/dispatches"
        payload = {"ref": self.branch}
        if self.inputs:
            payload["inputs"] = self.inputs

        logging.info(f"🔹 Triggering workflow {self.workflow_id} on branch {self.branch}...")
        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code != 204:
            logging.error(f"❌ Failed to trigger workflow: {response.text}")
            raise Exception(f"Failed to trigger workflow: {response.text}")

        logging.info("✅ Workflow triggered successfully.")
        return True

    def get_latest_run(self):
        """Fetches the latest run of the workflow."""
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/runs"

        logging.info("🔹 Fetching latest workflow run...")
        for _ in range(10):  # Retry logic
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                logging.error(f"❌ Failed to fetch workflow runs: {response.text}")
                raise Exception(f"Failed to fetch workflow runs: {response.text}")

            runs = response.json().get("workflow_runs", [])
            for run in runs:
                #logging.info(f"🔄 {run['id']} -- {run['name']} -- {self.workflow_id }")
                # if run["name"] == self.workflow_id and run["head_branch"] == self.branch:
                #     logging.info(f"✅ Found workflow run: ID {run['id']}")
                #     return run
                                
                if run["path"].endswith(self.workflow_id) and run["head_branch"] == self.branch:
                    logging.info(f"✅ Found workflow run: ID {run['id']}")
                    return run


            logging.info("🔄 No matching run found, retrying in 5 seconds...")
            time.sleep(5)

        raise Exception("No recent workflow run found.")

    def wait_for_completion(self, run_id):
        """Waits for the workflow run to complete."""
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/runs/{run_id}"

        logging.info(f"🔄 Waiting for workflow {run_id} to complete...")
        while True:
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                logging.error(f"❌ Failed to fetch run status: {response.text}")
                raise Exception(f"Failed to fetch run status: {response.text}")

            run_data = response.json()
            status = run_data["status"]
            conclusion = run_data.get("conclusion")
            logs_url = run_data["html_url"]
            duration = run_data.get("run_duration_ms", 0) / 1000  # Convert to seconds

            logging.info(f"🔹 Current status: {status}")

            if status == "completed":
                logging.info(f"✅ Workflow completed with conclusion: {conclusion}")
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
        logging.info(f"{result}")
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
        logging.info(f"{result}")
        print(json.dumps(result))  # Terraform puede capturar este output
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
