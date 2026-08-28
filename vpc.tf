# ---------------------------------------------------------------------------
# Minimal explicit networking for InfraFox.
#
# We do NOT rely on an AWS "default VPC" — some accounts (including this
# one, in ap-south-1) don't have one, and depending on an implicit,
# account-specific default is exactly the kind of hidden infrastructure
# dependency a FinOps/reliability-minded project should avoid in its own
# stack. Everything here is free: VPC, subnet, Internet Gateway, and route
# table carry no charge by themselves — only data transfer and attached
# compute/NAT resources cost money, and there is no NAT Gateway here.
#
# This is a single public subnet, single AZ, matching the "one instance,
# one region, no HA" MVP scope already agreed in ARCHITECTURE.md.
# ---------------------------------------------------------------------------

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "infrafox" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "infrafox-vpc"
  }
}

resource "aws_subnet" "infrafox_public" {
  vpc_id                  = aws_vpc.infrafox.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "infrafox-public-subnet"
  }
}

resource "aws_internet_gateway" "infrafox" {
  vpc_id = aws_vpc.infrafox.id

  tags = {
    Name = "infrafox-igw"
  }
}

resource "aws_route_table" "infrafox_public" {
  vpc_id = aws_vpc.infrafox.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.infrafox.id
  }

  tags = {
    Name = "infrafox-public-rt"
  }
}

resource "aws_route_table_association" "infrafox_public" {
  subnet_id      = aws_subnet.infrafox_public.id
  route_table_id = aws_route_table.infrafox_public.id
}
