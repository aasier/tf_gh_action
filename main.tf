resource "null_resource" "install_python_packages" {
  provisioner "local-exec" {
    command = "pip3 install -r ${path.module}/requirements.txt"
  }
}
data "external" "github_action" {
  depends_on = [null_resource.install_python_packages]
  program = [
    "python3", "${path.module}/github_action.py",
    "--token", var.github_token,                     # token
    "--repo", var.gh_repository,                     # Org/Repo
    "--workflow", var.gh_workflow_file,              # deploy.yaml
    "--branch", var.gh_branch,                       # main
    "--inputs", jsonencode(var.github_action_inputs) # "{}" 
  ]
}
