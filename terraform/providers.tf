terraform {
  required_version = ">= 1.10"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.0" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }

  backend "s3" {
    bucket       = "ticketdesk-tfstate-magarishi-2026" # from Execution Guide Phase 2.7
    key          = "poc/terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true # S3 native locking
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = var.project, Environment = "poc", ManagedBy = "terraform" }
  }
}

# WAF for CloudFront must be created in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  default_tags {
    tags = { Project = var.project, Environment = "poc", ManagedBy = "terraform" }
  }
}
