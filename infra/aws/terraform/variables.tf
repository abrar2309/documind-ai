variable "aws_region" {
  type = string
}
variable "name" {
  type    = string
  default = "documind"
}
variable "vpc_id" {
  type = string
}
variable "public_subnet_ids" {
  type = list(string)
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "acm_certificate_arn" {
  type = string
}
variable "backend_image" {
  type = string
}
variable "frontend_image" {
  type = string
}
variable "database_url_secret_arn" {
  type = string
}
variable "jwt_secret_arn" {
  type = string
}
variable "cors_allowed_origins" {
  type = string
}
variable "trusted_hosts" {
  type = string
}
variable "kafka_bootstrap_servers" {
  type = string
}
variable "redis_url_secret_arn" {
  type = string
}
variable "embedding_provider" {
  type    = string
  default = "openai"
}
variable "chat_provider" {
  type    = string
  default = "openai"
}
variable "ollama_base_url" {
  type    = string
  default = ""
}
variable "ollama_embedding_model" {
  type    = string
  default = "all-minilm"
}
variable "ollama_chat_model" {
  type    = string
  default = "qwen3:1.7b"
}
variable "extra_runtime_secrets" {
  type    = list(object({ name = string, valueFrom = string }))
  default = []
}
variable "alb_ingress_cidrs" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}
variable "backend_cpu" {
  type    = number
  default = 1024
}
variable "backend_memory" {
  type    = number
  default = 2048
}
variable "worker_cpu" {
  type    = number
  default = 1024
}
variable "worker_memory" {
  type    = number
  default = 2048
}
variable "frontend_cpu" {
  type    = number
  default = 256
}
variable "frontend_memory" {
  type    = number
  default = 512
}
variable "backend_desired_count" {
  type    = number
  default = 2
}
variable "worker_desired_count" {
  type    = number
  default = 1
}
variable "frontend_desired_count" {
  type    = number
  default = 2
}
variable "log_retention_days" {
  type    = number
  default = 30
}
variable "tags" {
  type    = map(string)
  default = { Project = "DocuMind", ManagedBy = "Terraform" }
}
