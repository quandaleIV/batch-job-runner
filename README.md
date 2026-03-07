# JobFlow | On-Demand Batch Job Platform on AWS

A cloud-native, event-driven batch compute platform built on AWS. A Discord slash command triggers an ephemeral EC2 worker via GitHub Actions and Terraform, runs a containerised job, stores output to S3, and self-destructs, leaving zero idle infrastructure and zero cost between runs.

---

## Architecture

```
Discord /run command
        │
        ▼
Lambda (Discord Bot)
        │
        ▼
API Gateway → GitHub Actions (repository_dispatch)
        │
        ▼
Terraform Apply
        │
        ▼
EC2 t3.micro spins up
        │
        ▼
cloud-init pulls Docker image from ECR
        │
        ▼
Job runs → output saved to S3
        │
        ▼
cloud-init triggers destroy workflow via GitHub API
        │
        ▼
Terraform Destroy → all resources terminated
        │
        ▼
CloudWatch failsafe → terminates any stuck instances via SNS + Lambda
```

---

## How It Works

1. User runs `/run job=image-resize` in Discord
2. Discord bot (AWS Lambda) receives the slash command
3. Lambda triggers a GitHub Actions `repository_dispatch` event via API Gateway
4. GitHub Actions runs Terraform to provision an EC2 instance
5. `cloud-init` bootstraps the instance — installs Docker, authenticates with ECR, pulls the correct job image
6. The Docker container runs the job and writes output to S3
7. On completion, `cloud-init` triggers the GitHub Actions destroy workflow via the GitHub API
8. Terraform destroys all provisioned resources — EC2, security group, IAM roles, CloudWatch alarm, SNS topic, failsafe Lambda
9. If the instance ever gets stuck running idle, a CloudWatch alarm detects CPU < 5% for 10 minutes and triggers an SNS notification → Lambda → EC2 termination

---

## AWS Services

| Service | Purpose |
|---|---|
| Lambda | Discord bot + CloudWatch failsafe handler |
| API Gateway | Receives Discord interactions |
| EC2 | Ephemeral compute for each job |
| ECR | Docker image registry for job containers |
| S3 | Job input/output storage + Terraform remote state |
| CloudWatch | CPU alarm for idle instance detection |
| SNS | Notification hub between CloudWatch and failsafe Lambda |
| IAM | Least-privilege roles for EC2, Lambda, GitHub Actions (OIDC) |
| SSM Parameter Store | Secure secrets storage — no hardcoded credentials |
| DynamoDB | Terraform state locking |

---

## Jobs

| Job | Description |
|---|---|
| `image-resize` | Fetches images from S3 input folder, compresses them, saves to S3 output folder |
| `pdf-report` | Fetches forex OHLCV data, runs technical analysis, generates a PDF report |
| `data-scrape` | Scrapes external data, processes and saves structured JSON to S3 |

Adding a new job type requires only a new Docker image pushed to ECR — the platform infrastructure is job-agnostic.

---

## Tech Stack

- **Terraform** — provisions all AWS infrastructure
- **GitHub Actions** — CI/CD pipeline, triggered via `repository_dispatch`
- **Docker** — each job packaged as an independent image
- **cloud-init** — bootstraps EC2, pulls correct ECR image, runs job
- **Python** — Discord bot, failsafe Lambda, job scripts
- **discord.py / ecdsa** — slash command handling and Ed25519 signature verification

---

## Setup

### Prerequisites
- AWS account with billing alerts configured
- GitHub repository with Actions enabled
- Discord application and bot token
- Terraform installed locally
- Docker installed locally

### 1. Clone the repo
```bash
git clone https://github.com/quandaleIV/batch-job-runner
cd batch-job-runner
```

### 2. Create S3 bucket and DynamoDB table for Terraform state
```bash
aws s3 mb s3://batch-job-runner-tfstate --region ap-southeast-2
aws dynamodb create-table \
  --table-name batch-job-runner-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-2
```

### 3. Store secrets in SSM Parameter Store
```bash
aws ssm put-parameter --name /batch-job-runner/discord-public-key --value "YOUR_VALUE" --type SecureString --region ap-southeast-2
aws ssm put-parameter --name /batch-job-runner/discord-token --value "YOUR_VALUE" --type SecureString --region ap-southeast-2
aws ssm put-parameter --name /batch-job-runner/discord-application-id --value "YOUR_VALUE" --type SecureString --region ap-southeast-2
aws ssm put-parameter --name /batch-job-runner/github-token --value "YOUR_VALUE" --type SecureString --region ap-southeast-2
aws ssm put-parameter --name /batch-job-runner/github-repo --value "YOUR_VALUE" --type SecureString --region ap-southeast-2
aws ssm put-parameter --name /batch-job-runner/twelve-data-api-key --value "YOUR_VALUE" --type SecureString --region ap-southeast-2
```

### 4. Set up GitHub Actions OIDC
Create an IAM role with OIDC trust for GitHub Actions and add the following secrets to your GitHub repo:
- `AWS_ROLE_ARN` — ARN of the GitHub Actions IAM role

### 5. Deploy the Discord bot Lambda
```bash
cd bot
docker run --rm -v $(pwd):/var/task --entrypoint pip public.ecr.aws/lambda/python:3.11 \
  install requests ecdsa -t /var/task/package/ --no-cache-dir
cp handler.py package/
cd package && zip -r ../lambda.zip . && cd ../..

aws lambda update-function-code \
  --function-name batch-job-discord-bot \
  --zip-file fileb://bot/lambda.zip \
  --region ap-southeast-2
```

### 6. Register Discord slash commands
```bash
cd bot
python3 register_commands.py
```

### 7. Set the Lambda Function URL as the Discord Interactions Endpoint URL
In the Discord Developer Portal → your app → General Information → Interactions Endpoint URL

### 8. Run a job
In your Discord server:
```
/run job=image-resize
```

---

## Cost

Each job run on a `t3.micro` instance costs approximately **$0.001–$0.003** depending on job duration. All infrastructure is destroyed after each run — there are no idle costs between jobs.

---

## Resume Bullets

```
• Built JobFlow, an on-demand batch compute platform on AWS — Discord slash command triggers 
  GitHub Actions via Lambda and API Gateway, Terraform provisions ephemeral EC2, cloud-init 
  pulls job-specific Docker image from ECR, output stored to S3, infrastructure self-destructs 
  on completion via automated Terraform destroy

• Designed job-agnostic architecture supporting multiple workload types via a containerised 
  job registry in ECR — adding a new job requires only a new Docker image, no infrastructure changes

• Implemented cost-optimisation failsafe using CloudWatch, SNS, and Lambda — automatically 
  terminates idle EC2 workers tagged as ephemeral after 10 minutes of CPU utilisation below 5%

• Configured OIDC trust between GitHub Actions and AWS — eliminated long-lived credentials 
  from the CI/CD pipeline entirely

• Secured all secrets in AWS SSM Parameter Store — no hardcoded credentials anywhere in 
  the codebase or CI/CD pipeline
```

---

## Repo Structure

```
batch-job-runner/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── .github/workflows/
│   ├── provision.yml
│   └── destroy.yml
├── jobs/
│   ├── image-resize/
│   ├── pdf-report/
│   └── data-scrape/
├── bot/
│   ├── handler.py
│   ├── register_commands.py
│   └── requirements.txt
├── failsafe/
│   ├── failsafe.py
│   └── failsafe.zip
├── scripts/
│   └── cloud-init.sh
└── README.md
```