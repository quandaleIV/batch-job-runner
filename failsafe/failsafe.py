import boto3

ec2 = boto3.client('ec2', region_name='ap-southeast-2')

def lambda_handler(event, context):
    # Find all running EC2 instances tagged as batch-job-runner
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['batch-job-runner']},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )

    instance_ids = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_ids.append(instance['InstanceId'])

    if instance_ids:
        print(f"Terminating idle instances: {instance_ids}")
        ec2.terminate_instances(InstanceIds=instance_ids)
    else:
        print("No idle instances found")

    return {'statusCode': 200}