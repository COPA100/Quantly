# rds wants a subnet group spanning 2+ azs even for a single-az instance
resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

# generated here so the password never lives in a tfvars file. no special
# characters, so it drops straight into a connection url without escaping.
resource "random_password" "master" {
  length  = 32
  special = false
}

resource "aws_db_instance" "this" {
  identifier = var.name

  engine                     = "postgres"
  engine_version             = var.engine_version
  auto_minor_version_upgrade = true

  # smallest tier, single-az: this stack is stood up for demos, not run 24/7
  instance_class    = var.instance_class
  multi_az          = false
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.username
  password = random_password.master.result

  # sits in a public subnet (there are no private ones) but gets no public ip,
  # and its security group only admits the api and worker
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = var.security_group_ids
  publicly_accessible    = false

  # teardown-friendly: data is reseeded on every stand-up, so no backups, no
  # final snapshot, and nothing blocking `terraform destroy`
  backup_retention_period = var.backup_retention_days
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true
}
