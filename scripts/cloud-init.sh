#!/bin/bash
yum update -y
yum install -y docker 
systemctl start docker
systemctl enable docker 
docker run --rm hello-world
echo "Job complete"