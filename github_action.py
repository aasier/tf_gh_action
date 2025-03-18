import requests
import time
import json
import argparse
import sys
import logging
import re
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
                outputs = self.get_run_outputs(run_id)
                return {
                    "status": status,
                    "conclusion": conclusion,
                    "logs_url": logs_url,
                    "duration_seconds": duration,
                    "outputs": outputs
                }

            time.sleep(10)

    def extract_outputs_from_logs(self, logs_content, job_name):
        """Extracts output variables from job logs using various patterns."""
        outputs = {}
        
        # Patrones para encontrar diferentes formatos de outputs
        patterns = [
            # Patrón para "Setting output" o similares
            r"Setting output\s+([^=\s]+)\s*=\s*(.+?)$",
            # Patrón para "::set-output name="
            r"::set-output name=([^:]+?)::(.+?)$",
            # Patrón para "echo {name}={value} >> $GITHUB_OUTPUT"
            r"echo\s+([^=\s]+)\s*=\s*(.+?)\s*>>\s*\$GITHUB_OUTPUT",
            # Patrón para "Add-Content" (PowerShell)
            r"Add-Content -Path \$env:GITHUB_OUTPUT -Value '([^=]+)=(.+?)'",
            # Patrón simple de "key=value" cerca de "output" o "GITHUB_OUTPUT"
            r"(?:output|GITHUB_OUTPUT).*?([^=\s]+)\s*=\s*(.+?)$",
            # Patrón para capturas de líneas que contienen key=value
            r"\'([^=\s]+)=(.+?)\'.*?(?:output|GITHUB_OUTPUT)",
        ]
        
        # Recorrer los logs línea por línea
        for line in logs_content.splitlines():
            # Probar cada patrón
            for pattern in patterns:
                matches = re.search(pattern, line, re.IGNORECASE)
                if matches:
                    key = matches.group(1).strip()
                    value = matches.group(2).strip()
                    output_key = f"{job_name}.output.{key}"
                    outputs[output_key] = value
                    logging.info(f"📤 Extracted from logs: {output_key} = {value}")
                    break  # Si encuentra un match, pasa a la siguiente línea
                    
        return outputs

    def get_run_outputs(self, run_id):
        """Fetches the outputs of the completed workflow run."""
        url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/runs/{run_id}/jobs"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            logging.error(f"❌ Failed to fetch run jobs: {response.text}")
            raise Exception(f"Failed to fetch run jobs: {response.text}")

        jobs = response.json().get("jobs", [])
        all_outputs = {}

        for job in jobs:
            job_id = job["id"]
            job_name = job["name"]
            logging.info(f"🔹 Processing job: {job_name} (ID: {job_id})")
            
            job_outputs = {}
            
            # 1. Obtener los outputs directamente del API (si están disponibles)
            steps = job.get("steps", [])
            for step in steps:
                step_name = step.get("name", "")
                step_number = step.get("number", 0)
                
                if "outputs" in step and step["outputs"]:
                    step_outputs = step["outputs"]
                    logging.info(f"📤 Found outputs in step {step_number}: {step_name}")
                    
                    for output_name, output_value in step_outputs.items():
                        output_key = f"{job_name}.step{step_number}.{output_name}"
                        job_outputs[output_key] = output_value
                        logging.info(f"📤 Output: {output_key} = {output_value}")
            
            # 2. Intentar extraer outputs de los logs
            try:
                logs_url = f"{GITHUB_API_URL}/repos/{self.repo}/actions/jobs/{job_id}/logs"
                logs_response = requests.get(logs_url, headers=self.headers)
                
                if logs_response.status_code == 200:
                    logs_content = logs_response.text
                    logging.info(f"📄 Analyzing logs for job: {job_name}")
                    
                    # Extraer outputs de los logs
                    log_outputs = self.extract_outputs_from_logs(logs_content, job_name)
                    job_outputs.update(log_outputs)
                else:
                    logging.warning(f"⚠️ Could not fetch logs for job {job_id}: {logs_response.status_code}")
            except Exception as e:
                logging.warning(f"⚠️ Error processing logs: {e}")
            
            # Añadir los outputs de este job al resultado final
            all_outputs[job_name] = job_outputs

        return all_outputs

    def run(self):
        """Runs the full process: trigger, wait, and return the result."""
        self.trigger_workflow()
        time.sleep(5)  # Allow time for workflow to appear

        latest_run = self.get_latest_run()
        result = self.wait_for_completion(latest_run["id"])

        logging.info(f"🏁 Final result: {json.dumps(result, indent=2)}")
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
        print(json.dumps(result))  # Terraform puede capturar este output
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        print(json.dumps({"error": str(e)}))
        sys.exit(1)