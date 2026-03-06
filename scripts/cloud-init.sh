#!/bin/bash
yum update -y
yum install -y docker 
systemctl start docker
systemctl enable docker

# Log in to ECR
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 515052777430.dkr.ecr.ap-southeast-2.amazonaws.com

# Pull the correct Docker Image from ECR
docker pull 515052777430.dkr.ecr.ap-southeast-2.amazonaws.com/batch-job/${job_name}:latest

# Run the job
docker run --rm \
  -e INPUT_BUCKET=batch-job-runner-data \
  -e OUTPUT_BUCKET=batch-job-runner-data \
  -e INPUT_PREFIX=input/ \
  -e OUTPUT_PREFIX=output/ \
  -e TWELVE_DATA_API_KEY=demo \
  515052777430.dkr.ecr.ap-southeast-2.amazonaws.com/batch-job/${job_name}:latest

echo "Job complete"

# Shut down the instance
shutdown -h now