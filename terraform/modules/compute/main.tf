data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_instance" "app" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = "t3.micro"
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [var.app_sg_id]
  iam_instance_profile        = var.instance_profile_name
  associate_public_ip_address = true
  # No key_name: no SSH key exists. Admin access is through SSM Session Manager.

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # containers sit one hop further; with 1 they get no credentials
  }

  root_block_device {
    volume_size = 10
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/../../../scripts/user_data.sh", {
    region          = var.region
    registry        = split("/", var.ecr_repo_url)[0]
    image_repo      = var.ecr_repo_url
    app_secret_name = var.secret_name
    s3_bucket       = var.attachments_bucket_name
  })
  user_data_replace_on_change = true

  tags = { Name = "${var.project}-app" }
}
