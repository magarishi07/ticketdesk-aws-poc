output "attachments_bucket_id" { value = aws_s3_bucket.attachments.id }
output "attachments_bucket_arn" { value = aws_s3_bucket.attachments.arn }
output "attachments_bucket_name" { value = aws_s3_bucket.attachments.bucket }
output "ecr_repo_url" { value = aws_ecr_repository.app.repository_url }
output "ecr_repo_arn" { value = aws_ecr_repository.app.arn }
