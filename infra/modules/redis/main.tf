resource "aws_elasticache_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

# single node, no replicas: redis here is the celery broker plus a price cache,
# both of which can be lost and rebuilt. reachable only from inside the vpc via
# its security group.
resource "aws_elasticache_cluster" "this" {
  cluster_id = var.name

  engine               = "redis"
  engine_version       = var.engine_version
  parameter_group_name = var.parameter_group_name
  node_type            = var.node_type
  num_cache_nodes      = 1
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = var.security_group_ids

  apply_immediately = true
}
