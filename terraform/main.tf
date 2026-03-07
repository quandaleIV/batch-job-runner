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

#give ec2 access to ecr
resource "aws_iam_role_policy_attachment" "ec2_ecr" {
  role = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
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
  user_data = templatefile("${path.module}/../scripts/cloud-init.sh", {
    job_name = var.job_name
  })

  #tag this resource
  tags = {
    Name = "batch-job-runner"
    Job = var.job_name
  }
}

# setup sns topic for CloudWatch alarm notifications
resource "aws_sns_topic" "idle_alert" {
  name = "batch-job-idle-alert"
}

# Create CloudWatch alarm, triggers when ec2 CPU < 5% for 2 consec 5-min periods"
resource "aws_cloudwatch_metric_alarm" "idle_ec2" {
  alarm_name = "batch-job-idle-ec2"
  comparison_operator = "LessThanThreshold"
  evaluation_periods = 2
  metric_name = "CPUUtilization"
  namespace = "AWS/EC2"
  period = 300
  statistic = "Average"
  threshold = 5
  alarm_actions = [aws_sns_topic.idle_alert.arn]
  dimensions = {InstanceId = aws_instance.batch_job.id }
}

# Create an IAM role for the failsafe lambda function
resource "aws_iam_role" "failsafe_lambda_role" {
  name = "batch-job-failsafe-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Attach policies to the failsafe lambda role
resource "aws_iam_role_policy" "failsafe_lambda_policy" {
  name = "batch-job-failsafe-lambda-policy"
  role = aws_iam_role.failsafe_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ec2:TerminateInstances", "ec2:DescribeInstances"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}

# Failsafe lambda function
resource "aws_lambda_function" "failsafe" {
  filename      = "${path.module}/../failsafe/failsafe.zip"
  function_name = "batch-job-failsafe"
  role          = aws_iam_role.failsafe_lambda_role.arn
  handler       = "failsafe.lambda_handler"
  runtime       = "python3.11"

  tags = {
    Name = "batch-job-failsafe"
  }
}

# Allow SNS to invoke the failsafe Lambda
resource "aws_lambda_permission" "sns_invoke_failsafe" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.failsafe.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.idle_alert.arn
}

# Subscribe Lambda to SNS topic
resource "aws_sns_topic_subscription" "failsafe_subscription" {
  topic_arn = aws_sns_topic.idle_alert.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.failsafe.arn
}











