variable "aws_region" {
  description = "AWS region. This project is single-region by design (ap-south-1 / Mumbai)."
  type        = string
  default     = "ap-south-1"

  validation {
    condition     = var.aws_region == "ap-south-1"
    error_message = "InfraFox is a single-region project. Do not point this at another region without re-checking EC2 instance-type availability and pricing there."
  }
}

variable "environment" {
  description = "Environment tag for all resources."
  type        = string
  default     = "development"
}

variable "instance_type" {
  description = "EC2 instance type. Must be one of the types confirmed available on this AWS account."
  type        = string
  default     = "t3.small"

  validation {
    condition     = contains(["t3.micro", "t3.small", "c7i-flex.large", "m7i-flex.large"], var.instance_type)
    error_message = "instance_type must be one of the four types confirmed available on this account: t3.micro, t3.small, c7i-flex.large, m7i-flex.large."
  }
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size in GB."
  type        = number
  default     = 20
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed to SSH into the instance. MUST be your current public IP in /32 form, e.g. 203.0.113.4/32. Never leave this as 0.0.0.0/0."
  type        = string

  validation {
    condition     = var.ssh_allowed_cidr != "0.0.0.0/0"
    error_message = "ssh_allowed_cidr must not be open to the world. Set it to your public IP in /32 form in terraform.tfvars."
  }
}

variable "budget_alert_email" {
  description = "Email address to receive AWS Budget threshold alerts (via SNS)."
  type        = string
}

variable "budget_limit_usd" {
  description = "Monthly budget ceiling in USD. Alerts fire at 50%/80%/100%/forecasted of this value."
  type        = number
  default     = 100
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access. Create this manually in the AWS console/CLI first — Terraform does not manage private key material."
  type        = string
}
