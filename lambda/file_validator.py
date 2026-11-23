import json
import logging
import os
import urllib.parse

import boto3

s3 = boto3.client('s3')
sns = boto3.client('sns')
log = logging.getLogger()
log.setLevel(logging.INFO)

TOPIC_ARN = os.environ['TOPIC_ARN']
MAX_BYTES = int(os.environ.get('MAX_BYTES', 5 * 1024 * 1024))

# allowed extension -> expected first bytes (empty list = plain text, no signature)
ALLOWED = {
    '.png': [b'\x89PNG'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.pdf': [b'%PDF'],
    '.txt': [],
    '.log': [],
}


def check(bucket, key, size):
    ext = os.path.splitext(key)[1].lower()
    if ext not in ALLOWED:
        return f'file type {ext or "(none)"} is not allowed'
    if size > MAX_BYTES:
        return f'file is {size} bytes, limit is {MAX_BYTES}'
    if ALLOWED[ext]:
        head = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-7')['Body'].read()
        if not any(head.startswith(sig) for sig in ALLOWED[ext]):
            return f'content does not match {ext} (possible disguised file)'
    return None


def handler(event, context):
    if os.environ.get('FORCE_FAIL') == 'true':
        raise RuntimeError('Forced failure to test the dead-letter queue')

    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        size = record['s3']['object'].get('size', 0)
        parts = key.split('/')
        ticket_id = parts[1] if len(parts) >= 3 else 'unknown'

        problem = check(bucket, key, size)
        if problem:
            s3.copy_object(Bucket=bucket, Key='quarantine/' + key,
                           CopySource={'Bucket': bucket, 'Key': key})
            s3.delete_object(Bucket=bucket, Key=key)
            result = 'QUARANTINED'
        else:
            s3.put_object_tagging(Bucket=bucket, Key=key,
                                  Tagging={'TagSet': [{'Key': 'scan', 'Value': 'passed'}]})
            result = 'ACCEPTED'

        log.info(json.dumps({'result': result, 'ticket': ticket_id, 'key': key,
                             'size': size, 'reason': problem}))
        message = (f'Ticket: #{ticket_id}\nFile: {key}\nSize: {size} bytes\nResult: {result}\n'
                   + (f'Reason: {problem}\n' if problem else ''))
        sns.publish(TopicArn=TOPIC_ARN,
                    Subject=f'TicketDesk: attachment {result.lower()} for ticket #{ticket_id}',
                    Message=message)
    return {'processed': len(event['Records'])}
