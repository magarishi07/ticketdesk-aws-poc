# TicketDesk – IT Support Ticket Tracker on AWS

TicketDesk lets employees raise IT support tickets with screenshots, lets engineers move them from Open to Closed, and gives managers a dashboard. This repository deploys it on AWS the way a real company would: secure by default, built from code, deployed by pipeline, monitored, and fully removable.

**Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · Docker · Terraform · GitHub Actions · AWS (ap-south-1)

## Architecture

Users → **CloudFront + WAF** (HTTPS) → **EC2** (Docker container, port 80 from CloudFront only) → **RDS PostgreSQL** (private subnets, no internet route).
Attachments → **S3** → **Lambda** validator (type, size, magic bytes) → **SNS** email; failures → **SQS** dead-letter queue.
**CloudWatch** logs, 6 alarms and a dashboard. **GuardDuty**, **CloudTrail**, **IAM Access Analyzer**, **VPC Flow Logs**. Secrets in **Secrets Manager**. Admin access via **SSM Session Manager** (no SSH).

## Repository layout

```text
app/                  FastAPI application (main.py, config.py, db.py, models.py, storage.py, templates/, static/)
Dockerfile            Container image (non-root, health check)
docker-compose.yml    Local stack: PostgreSQL + app
lambda/               S3-triggered file validator
scripts/user_data.sh  EC2 bootstrap (Docker + ticketdesk-deploy command)
terraform/            Root module + 10 modules: network, database, iam, compute, cdn, waf, storage, serverless, monitoring, security
tests/unit/           Unit tests (SQLite, run in CI)
tests/api/            API tests against a deployed URL
.github/workflows/    ci.yml, terraform-plan.yml, deploy.yml
docs/                 evidence/, issues.md, test-results.txt
```

## Run locally

```bash
cp .env.example .env        # then replace every value
docker compose up --build   # http://localhost:8000  (user: admin, password: ADMIN_PASSWORD from .env)
```

Unit tests: `pip install -r app/requirements.txt -r requirements-dev.txt && cd app && python -m pytest ../tests/unit -v`

## Deploy to AWS

1. Create an S3 bucket for Terraform state and put its name in `terraform/providers.tf` (`bucket = ...`).
2. `cp terraform/terraform.tfvars.example terraform/terraform.tfvars` and fill in the values.
3. Build:
   ```bash
   cd terraform
   terraform init && terraform validate
   terraform plan -out tfplan
   terraform apply tfplan
   terraform output
   ```
4. Confirm the SNS subscription email.
5. First image:
   ```bash
   REPO=$(terraform -chdir=terraform output -raw ecr_repo_url)
   aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin ${REPO%%/*}
   docker build -t $REPO:latest . && docker push $REPO:latest
   aws ssm send-command --instance-ids $(terraform -chdir=terraform output -raw instance_id) \
     --document-name AWS-RunShellScript --parameters 'commands=["/usr/local/bin/ticketdesk-deploy latest"]'
   aws s3 sync app/static s3://$(terraform -chdir=terraform output -raw frontend_bucket)/static
   ```
6. Open `terraform output -raw app_url`. Admin password: Secrets Manager → `ticketdesk/app` → `admin_password`.
7. Pipeline: add the GitHub repository variables listed in the POC document (section 17.6), create the `production` environment with a required reviewer, and protect `main`.

## Remove everything

```bash
cd terraform && terraform destroy
```

## Team

| Name | Role | Owns |
| --- | --- | --- |
| [Person 1] | Application & Container Engineer | `app/`, Docker, `modules/compute`, `modules/cdn`, `deploy.yml`, `tests/unit` |
| [Person 2] | DevOps & Security Engineer | Terraform root, `modules/network`, `database`, `iam`, `waf`, `security`, `terraform-plan.yml` |
| [Person 3] | Serverless, Monitoring & QA Engineer | `lambda/`, `modules/storage`, `serverless`, `monitoring`, `ci.yml`, `tests/api` |
