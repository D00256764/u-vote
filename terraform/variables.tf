variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Prefix for resource names and tags"
  type        = string
  default     = "uvote"
}

variable "environment" {
  description = "Environment label (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "uvote"
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS control plane"
  type        = string
  default     = "1.31"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway for all private subnets (lower cost, less HA)"
  type        = bool
  default     = true
}

variable "eks_node_instance_types" {
  description = "EC2 instance types for EKS managed node groups"
  type        = list(string)
  default     = ["c7i-flex.large"]
}

variable "eks_node_desired_size" {
  type    = number
  default = 2
}

variable "eks_node_min_size" {
  type    = number
  default = 1
}

variable "eks_node_max_size" {
  type    = number
  default = 4
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "voting_db"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "uvote_admin"
}

variable "db_password" {
  description = "PostgreSQL master password (set in terraform.tfvars — never commit)"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GiB"
  type        = number
  default     = 20
}

variable "db_backup_retention_days" {
  type    = number
  default = 0
}

variable "db_deletion_protection" {
  type    = bool
  default = false
}

variable "db_skip_final_snapshot" {
  type    = bool
  default = true
}

variable "ecr_services" {
  description = "Microservice names — one ECR repository per service"
  type        = list(string)
  default = [
    "auth-service",
    "admin-service",
    "voting-service",
    "results-service",
    "election-service",
    "frontend-service",
  ]
}

variable "tags" {
  description = "Additional tags applied to all taggable resources"
  type        = map(string)
  default     = {}
}
