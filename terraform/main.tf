module "network" {
  source  = "./modules/network"
  project = var.project
  region  = var.region
}

module "database" {
  source             = "./modules/database"
  project            = var.project
  private_subnet_ids = module.network.private_subnet_ids
  db_sg_id           = module.network.db_sg_id
  instance_class     = var.db_instance_class
}

module "storage" {
  source  = "./modules/storage"
  project = var.project
}

module "serverless" {
  source                 = "./modules/serverless"
  project                = var.project
  attachments_bucket_id  = module.storage.attachments_bucket_id
  attachments_bucket_arn = module.storage.attachments_bucket_arn
  alert_email            = var.alert_email
}

module "security" {
  source  = "./modules/security"
  project = var.project
  region  = var.region
}

module "waf" {
  source    = "./modules/waf"
  providers = { aws = aws.us_east_1 }
  project   = var.project
}

module "compute" {
  source                  = "./modules/compute"
  project                 = var.project
  region                  = var.region
  subnet_id               = module.network.public_subnet_ids[0]
  app_sg_id               = module.network.app_sg_id
  instance_profile_name   = module.iam.instance_profile_name
  secret_name             = module.database.secret_name
  attachments_bucket_name = module.storage.attachments_bucket_name
  ecr_repo_url            = module.storage.ecr_repo_url
}

module "cdn" {
  source        = "./modules/cdn"
  project       = var.project
  origin_domain = module.compute.public_dns
  web_acl_arn   = module.waf.web_acl_arn
}

module "monitoring" {
  source          = "./modules/monitoring"
  project         = var.project
  region          = var.region
  instance_id     = module.compute.instance_id
  db_identifier   = module.database.db_identifier
  function_name   = module.serverless.function_name
  alarm_topic_arn = module.serverless.topic_arn
}

module "iam" {
  source                 = "./modules/iam"
  project                = var.project
  region                 = var.region
  secret_arn             = module.database.secret_arn
  attachments_bucket_arn = module.storage.attachments_bucket_arn
  ecr_repo_arn           = module.storage.ecr_repo_arn
  app_log_group_arn      = module.monitoring.app_log_group_arn
  frontend_bucket_arn    = module.cdn.frontend_bucket_arn
  distribution_arn       = module.cdn.distribution_arn
  instance_arn           = module.compute.instance_arn
  github_repo            = var.github_repo
  state_bucket           = var.state_bucket
}
