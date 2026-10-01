output "address" {
  value = aws_elasticache_cluster.this.cache_nodes[0].address
}

output "port" {
  value = aws_elasticache_cluster.this.cache_nodes[0].port
}

# host:port prefix, callers append the db number (redis://host:6379/0)
output "url" {
  value = "redis://${aws_elasticache_cluster.this.cache_nodes[0].address}:${aws_elasticache_cluster.this.cache_nodes[0].port}"
}
