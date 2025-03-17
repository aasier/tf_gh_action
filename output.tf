output "github_action_result" {
  value = data.external.github_action
}

# output "deployment_status" {
#   value = data.external.github_action.result["outputs"]["deploy_status"]
# }

# output "deployment_message" {
#   value = data.external.github_action.result["outputs"]["deploy_message"]
# }