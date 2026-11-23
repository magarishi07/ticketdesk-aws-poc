output "guardduty_detector_id" { value = aws_guardduty_detector.main.id }
output "trail_bucket" { value = aws_s3_bucket.trail.bucket }
