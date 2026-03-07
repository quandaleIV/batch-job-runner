#!/bin/bash
yum update -y
yum install -y docker 
systemctl start docker
systemctl enable docker

# Log in to ECR
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 515052777430.dkr.ecr.ap-southeast-2.amazonaws.com

# Fetch secrets from SSM
TWELVE_DATA_API_KEY=$(aws ssm get-parameter --name /batch-job-runner/twelve-data-api-key --with-decryption --region ap-southeast-2 --query Parameter.Value --output text)
GITHUB_TOKEN=$(aws ssm get-parameter --name /batch-job-runner/github-token --with-decryption --region ap-southeast-2 --query Parameter.Value --output text)
GITHUB_REPO=$(aws ssm get-parameter --name /batch-job-runner/github-repo --with-decryption --region ap-southeast-2 --query Parameter.Value --output text)

# Pull the correct Docker Image from ECR
docker pull 515052777430.dkr.ecr.ap-southeast-2.amazonaws.com/batch-job/${job_name}:latest

# Run the job
docker run --rm \
  -e INPUT_BUCKET=batch-job-runner-data \
  -e OUTPUT_BUCKET=batch-job-runner-data \
  -e INPUT_PREFIX=input/ \
  -e OUTPUT_PREFIX=output/ \
  -e TWELVE_DATA_API_KEY=$TWELVE_DATA_API_KEY \
  515052777430.dkr.ecr.ap-southeast-2.amazonaws.com/batch-job/${job_name}:latest

echo "Job complete"

# Trigger destroy workflow
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/${github_repo}/actions/workflows/destroy.yml/dispatches \
  -d '{"ref":"main"}'

# Shut down the instance
shutdown -h now