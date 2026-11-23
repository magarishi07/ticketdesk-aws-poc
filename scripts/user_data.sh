#!/bin/bash
# EC2 bootstrap, rendered by Terraform templatefile().
# Dollar-brace values are filled by Terraform; a doubled dollar passes a literal dollar to bash.
set -euxo pipefail

dnf install -y docker
systemctl enable --now docker

cat > /usr/local/bin/ticketdesk-deploy <<'EOF'
#!/bin/bash
set -euo pipefail
TAG=$${1:-latest}
aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin ${registry}
docker pull ${image_repo}:$TAG
docker rm -f ticketdesk 2>/dev/null || true
docker run -d --name ticketdesk --restart always -p 80:8000 \
  -e APP_SECRET_NAME=${app_secret_name} \
  -e S3_BUCKET=${s3_bucket} \
  -e AWS_REGION=${region} \
  --log-driver awslogs \
  --log-opt awslogs-region=${region} \
  --log-opt awslogs-group=/ticketdesk/app \
  --log-opt awslogs-stream=$(hostname) \
  ${image_repo}:$TAG
docker image prune -f
EOF
chmod +x /usr/local/bin/ticketdesk-deploy

# First start. If no image exists yet, the first pipeline run (or a manual push) deploys it.
/usr/local/bin/ticketdesk-deploy latest || echo "No image in ECR yet - push one, then run ticketdesk-deploy"
