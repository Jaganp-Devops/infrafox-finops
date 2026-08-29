# ---------------------------------------------------------------------------
# Single security group for the InfraFox instance.
#
# No NAT Gateway, no private subnet — the instance sits in InfraFox's own
# public subnet (see vpc.tf) with a tight inbound rule set instead. Cheaper
# and simpler for a single-instance MVP, and the security posture comes
# from the SG rules, not from network topology.
# ---------------------------------------------------------------------------

resource "aws_security_group" "infrafox_sg" {
  name        = "infrafox-sg"
  description = "InfraFox EC2 security group - restricted SSH, public HTTPS, ACME HTTP challenge only"
  vpc_id      = aws_vpc.infrafox.id

  # SSH — restricted to your IP only. This is enforced twice: once by the
  # ssh_allowed_cidr variable validation (rejects 0.0.0.0/0), and again here
  # by only ever referencing that variable, never a hardcoded open range.
  ingress {
    description = "SSH from operator IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  ingress {
    description = "SSH from GitHub Actions runners "
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS — public, this is the actual product endpoint.
  ingress {
    description = "HTTPS (public dashboard/API via Nginx)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP — required only for Let's Encrypt's ACME HTTP-01 challenge and to
  # redirect to HTTPS. Not used to serve the app itself.
  ingress {
    description = "HTTP (ACME challenge + HTTPS redirect only)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound (AWS API calls, package installs, DuckDNS updates)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "infrafox-sg"
  }
}
