output "db_identifier" { value = aws_db_instance.main.identifier }
output "db_address" { value = aws_db_instance.main.address }
output "secret_arn" { value = aws_secretsmanager_secret.app.arn }
output "secret_name" { value = aws_secretsmanager_secret.app.name }
