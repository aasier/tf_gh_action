variable "github_token" {
  type      = string
  sensitive = true
}

variable "gh_repository" {
  type = string
}

variable "gh_workflow_file" {
  type    = string
  default = "example.yaml"
}

variable "github_action_inputs" {
  type = map(string)
}

variable "gh_branch" {
  type = string
}

