import requests
import boto3

ssm = boto3.client('ssm', region_name='ap-southeast-2')

def get_parameter(name):
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

DISCORD_TOKEN = get_parameter('/batch-job-runner/discord-token')
APPLICATION_ID = get_parameter('/batch-job-runner/discord-application-id')

url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

command = {
    "name": "run",
    "description": "Run a batch job",
    "options": [
        {
            "name": "job",
            "description": "Job to run",
            "type": 3,
            "required": True,
            "choices": [
                {"name": "image-resize", "value": "image-resize"},
                {"name": "pdf-report", "value": "pdf-report"},
                {"name": "data-scrape", "value": "data-scrape"}
            ]
        }
    ]
}

response = requests.post(url, headers={
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json"
}, json=command)

print(response.status_code, response.json())