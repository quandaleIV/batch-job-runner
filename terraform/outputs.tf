output "instance_id" {
  value = aws_instance.batch_job.id
}
output "public_ip" {
  value = aws_instance.batch_job.public_ip
}

