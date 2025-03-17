variable "github_token" {
    type = string
    sensitive = true
}

variable "gh_repository" {
    type = string
}

variable "gh_workflow"_file {
    type = string
}

variable "gh_workflow_inputs" {
    type = string
    default = "{}"
}

variable "gh_branch" {
    type = string
}

