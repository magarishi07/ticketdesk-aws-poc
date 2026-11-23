output "function_name" { value = aws_lambda_function.validator.function_name }
output "topic_arn" { value = aws_sns_topic.alerts.arn }
output "dlq_name" { value = aws_sqs_queue.dlq.name }
