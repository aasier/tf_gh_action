# provider requirements
terraform {
  required_version = ">= 1.9" 
}

terraform {
  required_providers {
    external = {
      source = "hashicorp/external"
      version = "2.3.4"
    }
  }
}

provider "external" {
  # Configuration options
}