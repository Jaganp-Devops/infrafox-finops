output "instance_id" {
  description = "EC2 instance ID — use for stop/start/terminate commands and cost tracking."
  value       = aws_instance.infrafox.id
}

output "public_ip" {
  description = "Current public IPv4. Push this to DuckDNS after every instance start (see scripts/duckdns-update.sh)."
  value       = aws_instance.infrafox.public_ip
}

output "instance_type" {
  value = aws_instance.infrafox.instance_type
}

output "iam_role_arn" {
  value = aws_iam_role.infrafox_ec2_role.arn
}

output "security_group_id" {
  value = aws_security_group.infrafox_sg.id
}

output "sns_topic_arn" {
  description = "Confirm the email subscription to this topic after apply, or budget alerts will not be delivered."
  value       = aws_sns_topic.budget_alerts.arn
}

output "ssh_command" {
  description = "Convenience SSH command using your configured key pair."
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_instance.infrafox.public_ip}"
}
