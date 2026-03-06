import json
import requests
import boto3

from ecdsa import VerifyingKey, Ed25519

ssm = boto3.client('ssm', region_name='ap-southeast-2')

def verify_key(body, signature, timestamp, public_key_hex):
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=Ed25519)
        vk.verify(bytes.fromhex(signature), (timestamp + body).encode())
        return True
    except Exception:
        return False

def get_parameter(name):
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

DISCORD_PUBLIC_KEY = get_parameter('/batch-job-runner/discord-public-key')
GITHUB_TOKEN = get_parameter('/batch-job-runner/github-token')
GITHUB_REPO = get_parameter('/batch-job-runner/github-repo')

def trigger_github_actions(job_name):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    payload = {
        'event_type': 'run-job',
        'client_payload': {
            'job_name': job_name
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code == 204

def lambda_handler(event, context):
    body = event.get('body', '{}')
    headers = event.get('headers', {})

    signature = headers.get('x-signature-ed25519', '')
    timestamp = headers.get('x-signature-timestamp', '')

    raw_body = body if isinstance(body, str) else json.dumps(body)

    if not verify_key(raw_body, signature, timestamp, DISCORD_PUBLIC_KEY):
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Invalid signature'})
        }

    body_dict = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    interaction_type = body_dict.get('type')

    if interaction_type == 1:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'type': 1})
        }

    if interaction_type == 2:
        command = body_dict['data']['name']

        if command == 'run':
            options = body_dict['data'].get('options', [])
            job_name = next((o['value'] for o in options if o['name'] == 'job'), 'hello-world')

            valid_jobs = ['image-resize', 'pdf-report', 'data-scrape']
            if job_name not in valid_jobs:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'type': 4,
                        'data': {
                            'content': f'Invalid job. Valid options: {", ".join(valid_jobs)}'
                        }
                    })
                }

            success = trigger_github_actions(job_name)
            message = f'Starting job `{job_name}`. Check S3 output in 5 minutes.' if success else f'Failed to trigger `{job_name}`.'

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'type': 4,
                    'data': {'content': message}
                })
            }

    return {
        'statusCode': 400,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Unknown interaction type'})
    }