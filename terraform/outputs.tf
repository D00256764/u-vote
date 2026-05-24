output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (EKS nodes, RDS)"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks.cluster_arn
}

output "eks_cluster_security_group_id" {
  description = "Security group attached to the EKS control plane"
  value       = module.eks.cluster_security_group_id
}

output "eks_node_security_group_id" {
  description = "Security group for EKS worker nodes"
  value       = module.eks.node_security_group_id
}

output "eks_oidc_provider_arn" {
  description = "IAM OIDC provider ARN for IRSA"
  value       = module.eks.oidc_provider_arn
}

output "configure_kubectl" {
  description = "Command to merge kubeconfig for this cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL hostname (use from EKS via external secret / env)"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.postgres.db_name
}

output "ecr_repository_urls" {
  description = "Map of service name to ECR repository URL"
  value = {
    for name, repo in aws_ecr_repository.services :
    name => repo.repository_url
  }
}

output "ecr_registry_id" {
  description = "AWS account ID used as ECR registry"
  value       = data.aws_caller_identity.current.account_id
}

output "iam_cluster_role_arn" {
  description = "IAM role ARN for the EKS cluster control plane"
  value       = module.eks.cluster_iam_role_arn
}

output "iam_node_role_arn" {
  description = "IAM role ARN for EKS worker nodes"
  value       = module.eks.eks_managed_node_groups["default"].iam_role_arn
}

output "ci_iam_user_name" {
  description = "IAM username for GitHub Actions CI"
  value       = aws_iam_user.ci.name
}

output "ci_access_key_id" {
  description = "AWS_ACCESS_KEY_ID — add to GitHub Actions secrets"
  value       = aws_iam_access_key.ci.id
}

output "ci_secret_access_key" {
  description = "AWS_SECRET_ACCESS_KEY — add to GitHub Actions secrets"
  value       = aws_iam_access_key.ci.secret
  sensitive   = true
}

output "github_secrets_summary" {
  description = "Values to set as GitHub Actions secrets"
  value = {
    AWS_ACCOUNT_ID    = data.aws_caller_identity.current.account_id
    AWS_REGION        = var.aws_region
    AWS_ACCESS_KEY_ID = aws_iam_access_key.ci.id
    EKS_CLUSTER_NAME  = module.eks.cluster_name
  }
}
