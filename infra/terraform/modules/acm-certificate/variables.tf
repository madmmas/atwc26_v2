variable "zone_name" {
  description = "Route53 public hosted zone name (e.g. atwc26.com)."
  type        = string
}

variable "domain_name" {
  description = "Primary ACM certificate domain name."
  type        = string
}

variable "subject_alternative_names" {
  description = "Additional names on the certificate (e.g. www.atwc26.com)."
  type        = list(string)
  default     = []
}

variable "validation_record_ttl" {
  description = "TTL for ACM DNS validation records."
  type        = number
  default     = 60
}

variable "tags" {
  description = "Tags applied to ACM resources."
  type        = map(string)
  default     = {}
}
