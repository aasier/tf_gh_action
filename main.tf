data "external" "github_action" {
  program = [
    "python3", "${path.module}/github_action.py",
    "--token", var.github_token, # token
    "--repo", var.gh_repository, # Org/Repo
    "--workflow", var.gh_workflow_file, # deploy.yaml
    "--branch", var.gh_branch, # main
    "--inputs", var.gh_workflow_inputs # "{}" 
  ]
}
