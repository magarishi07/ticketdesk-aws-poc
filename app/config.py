import json
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()  # reads .env on a laptop; does nothing on EC2


def _load_secret():
    name = os.getenv('APP_SECRET_NAME')
    if not name:
        return {}
    import boto3
    sm = boto3.client('secretsmanager', region_name=os.getenv('AWS_REGION', 'ap-south-1'))
    return json.loads(sm.get_secret_value(SecretId=name)['SecretString'])


class Settings:
    def __init__(self):
        s = _load_secret()
        if s:  # running on AWS: everything comes from Secrets Manager
            self.database_url = (
                f"postgresql+psycopg2://{s['username']}:{quote_plus(s['password'])}"
                f"@{s['host']}:{s['port']}/{s['dbname']}?sslmode=require"
            )
            self.session_secret = s['session_secret']
            self.admin_password = s['admin_password']
        else:  # running locally: values come from .env
            self.database_url = os.environ['DATABASE_URL']
            self.session_secret = os.environ['SESSION_SECRET']
            self.admin_password = os.getenv('ADMIN_PASSWORD')
        self.s3_bucket = os.getenv('S3_BUCKET')  # empty locally = files saved to disk
        self.aws_region = os.getenv('AWS_REGION', 'ap-south-1')
        self.max_upload_mb = 5


settings = Settings()
