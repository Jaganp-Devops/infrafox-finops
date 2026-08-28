# ---------------------------------------------------------------------------
# Single EC2 instance — the entire InfraFox stack runs here via Docker
# Compose (Nginx + FastAPI + Postgres). No ASG, no LB, no multi-AZ.
#
# Instance type is t3.small by default (see ARCHITECTURE.md §7 for the
# reasoning) and is constrained by variable validation to only the four
# instance types confirmed available on this account.
# ---------------------------------------------------------------------------

data "aws_ami" "ubuntu_2204" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "infrafox" {
  ami                    = data.aws_ami.ubuntu_2204.id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  subnet_id              = aws_subnet.infrafox_public.id
  vpc_security_group_ids = [aws_security_group.infrafox_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.infrafox_ec2_profile.name

  # No Elastic IP allocated — see ARCHITECTURE.md §8. As long as the instance
  # isn't stopped/started repeatedly, the public IP stays stable; a
  # cron @reboot script re-pushes the current IP to DuckDNS if it does
  # change. This avoids the classic "allocated-but-unattached EIP" waste
  # pattern that InfraFox's own rule engine (EIP-001) is designed to catch.
  associate_public_ip_address = true

  root_block_device {
    volume_type           = "gp3"
    volume_size            = var.root_volume_size_gb
    encrypted              = true
    delete_on_termination  = true # no orphaned volume left behind on teardown
  }

  metadata_options {
    http_tokens   = "required" # IMDSv2 only — IMDSv1 is a known SSRF vector
    http_endpoint = "enabled"
  }

  tags = {
    Name        = "infrafox-app"
    Application = "infrafox"
    Owner       = "jagan"
    Environment = var.environment
  }

  lifecycle {
    # Prevent Terraform from silently replacing the instance (and losing
    # local Postgres data) if the AMI updates upstream. Re-image
    # deliberately, not accidentally.
    ignore_changes = [ami]
  }
}
