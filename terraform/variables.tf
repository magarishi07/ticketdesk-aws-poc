variable "project" {
  description = "Name prefix and Project tag for every resource"
  default     = "ticketdesk"
}

variable "region" {
  description = "Main AWS region"
  default     = "ap-south-1"
}

variable "alert_email" {
  description = "Team email for SNS upload alerts and CloudWatch alarms"
}

variable "db_instance_class" {
  description = "RDS instance size"
  default     = "db.t3.micro"
}

variable "github_repo" {
  description = "GitHub repo in OIDC subject form: owner@ownerId/repo@repoId (GitHub immutable-ID subject claims)"
}

variable "state_bucket" {
  description = "Name of the Terraform state bucket"
}
