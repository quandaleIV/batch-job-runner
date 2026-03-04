terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "batch-job-runner-tfstate"
    key = "terraform.tfstate"
    region = "ap-southeast-2"
    dynamodb_table = "batch-job-runner-tflock"
  }
}

provider "aws" {
  region = var.aws_region
}

#create security group, allow SSH and outbound traffic
resource "aws_security_group" "batch_job" {
  name = "batch-job-runner-sg"
  description = "Security group for batch job runner"

  ingress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["58.111.102.250/32"]
  }

  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

#create IAM role for EC2 instance
resource "aws_iam_role" "ec2_role" {
  name = "batch_job-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

#attach policy to iam role
resource "aws_iam_role_policy_attachment" "ec2_s3" {
  role = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

#create instance profile for ec2 instance
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "batch-job-ec2-profile"
  role = aws_iam_role.ec2_role.name
}


#EC2 instance
resource "aws_instance" "batch_job" {
  ami = "ami-0a11f7293cd9a562e"
  instance_type = "t3.micro"
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name
  vpc_security_group_ids = [aws_security_group.batch_job.id]

  #run script as soon as instance starts up
  user_data = file("${path.module}/../scripts/cloud-init.sh")

  #tag this resource
  tags = {
    Name = "batch-job-runner"
    Job = var.job_name
  }
}









