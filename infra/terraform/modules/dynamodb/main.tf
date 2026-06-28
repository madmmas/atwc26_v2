resource "aws_dynamodb_table" "manifest" {
  name         = "${var.name_prefix}-${var.environment}-data-manifest"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  tags = merge(var.tags, { Component = "dynamodb-manifest" })
}
