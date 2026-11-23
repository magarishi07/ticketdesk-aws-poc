resource "random_password" "db" {
  length           = 24
  special          = true
  override_special = "!#%^*-_=+" # RDS rejects / @ " and spaces
}

resource "random_password" "session" {
  length  = 48
  special = false
}

resource "random_password" "admin" {
  length  = 16
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db-subnets"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "main" {
  identifier              = "${var.project}-db"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = var.instance_class
  allocated_storage       = 20
  storage_type            = "gp3"
  storage_encrypted       = true
  db_name                 = "ticketdesk"
  username                = "ticketdesk_admin"
  password                = random_password.db.result
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [var.db_sg_id]
  publicly_accessible     = false
  multi_az                = false
  backup_retention_period = 1
  skip_final_snapshot     = true # POC only
  deletion_protection     = false
  apply_immediately       = true
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "${var.project}/app"
  description             = "TicketDesk DB connection and app secrets"
  recovery_window_in_days = 0 # delete immediately on destroy (POC only)
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    username       = aws_db_instance.main.username
    password       = random_password.db.result
    host           = aws_db_instance.main.address
    port           = aws_db_instance.main.port
    dbname         = aws_db_instance.main.db_name
    session_secret = random_password.session.result
    admin_password = random_password.admin.result
  })
}
