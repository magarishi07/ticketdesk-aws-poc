import os
import re
import uuid

import boto3

from config import settings

_s3 = boto3.client('s3', region_name=settings.aws_region) if settings.s3_bucket else None


def _clean(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]', '_', name)[:100]


def save(ticket_id: int, filename: str, data: bytes, content_type: str | None) -> str:
    key = f'attachments/{ticket_id}/{uuid.uuid4().hex}-{_clean(filename)}'
    if _s3:
        _s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=data,
                       ContentType=content_type or 'application/octet-stream')
    else:
        path = os.path.join('uploads', key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
    return key


def url(key: str) -> str:
    if _s3:
        return _s3.generate_presigned_url(
            'get_object', Params={'Bucket': settings.s3_bucket, 'Key': key}, ExpiresIn=300)
    return f'/files/{key}'
