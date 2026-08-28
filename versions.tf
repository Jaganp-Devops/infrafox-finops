terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state for MVP — a single-developer project doesn't justify an S3
  # backend + DynamoDB lock table (extra ~$1-2/mo and setup complexity for
  # zero real benefit at this scale). Revisit only if a second collaborator
  # joins or you want state versioning.
  #
  # backend "local" is the default, so no explicit block is required.
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "infrafox"
      ManagedBy   = "terraform"
      Environment = var.environment
      Owner       = "jagan"
    }
  }
}
