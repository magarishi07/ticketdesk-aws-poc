data "aws_caller_identity" "current" {}

data "archive_file" "validator" {
  type        = "zip"
  source_file = "${path.module}/../../../lambda/file_validator.py"
  output_path = "${path.module}/../../../lambda/file_validator.zip"
}

# ---------- SNS ----------
resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email # click the confirmation link in the email!
}

# ---------- SQS dead-letter queue ----------
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project}-validator-dlq"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
}

# ---------- Lambda ----------
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project}-file-validator"
  retention_in_days = 7
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
  statement {
    sid       = "InspectAttachments"
    actions   = ["s3:GetObject", "s3:PutObjectTagging", "s3:DeleteObject"]
    resources = ["${var.attachments_bucket_arn}/attachments/*"]
  }
  statement {
    sid       = "WriteQuarantine"
    actions   = ["s3:PutObject"]
    resources = ["${var.attachments_bucket_arn}/quarantine/*"]
  }
  statement {
    sid       = "Notify"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
  statement {
    sid       = "SendToDlq"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.dlq.arn]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${var.project}-lambda-least-privilege"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "validator" {
  function_name    = "${var.project}-file-validator"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "file_validator.handler"
  filename         = data.archive_file.validator.output_path
  source_code_hash = data.archive_file.validator.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      TOPIC_ARN = aws_sns_topic.alerts.arn
      MAX_BYTES = "5242880"
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
}

resource "aws_lambda_function_event_invoke_config" "validator" {
  function_name                = aws_lambda_function.validator.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 3600
}

resource "aws_lambda_permission" "s3" {
  statement_id   = "AllowS3Invoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.validator.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = var.attachments_bucket_arn
  source_account = data.aws_caller_identity.current.account_id
}

# Prefix filter stops the Lambda from triggering itself when it writes to quarantine/
resource "aws_s3_bucket_notification" "attachments" {
  bucket = var.attachments_bucket_id
  lambda_function {
    lambda_function_arn = aws_lambda_function.validator.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "attachments/"
  }
  depends_on = [aws_lambda_permission.s3]
}

resource "aws_cloudwatch_metric_alarm" "dlq" {
  alarm_name          = "${var.project}-dlq-has-messages"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
