data "aws_route53_zone" "atwc26" {
  count = var.manage_dns_alias_records ? 1 : 0

  name         = var.domain_zone_name
  private_zone = false
}

locals {
  dns_alias_names = var.manage_dns_alias_records ? distinct(concat([var.domain_name], var.domain_subject_alternative_names)) : []
}

resource "aws_route53_record" "cloudfront_alias" {
  for_each = var.manage_dns_alias_records ? toset(local.dns_alias_names) : toset([])

  zone_id = data.aws_route53_zone.atwc26[0].zone_id
  name    = each.value
  type    = "A"

  alias {
    name                   = module.frontend_cdn.cloudfront_domain_name
    zone_id                = module.frontend_cdn.cloudfront_hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "cloudfront_alias_ipv6" {
  for_each = var.manage_dns_alias_records ? toset(local.dns_alias_names) : toset([])

  zone_id = data.aws_route53_zone.atwc26[0].zone_id
  name    = each.value
  type    = "AAAA"

  alias {
    name                   = module.frontend_cdn.cloudfront_domain_name
    zone_id                = module.frontend_cdn.cloudfront_hosted_zone_id
    evaluate_target_health = false
  }
}
