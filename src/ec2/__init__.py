import boto3

import ec2.requests

client = boto3.client("ec2")


def fetch_latest_image_id(distribution: str) -> str:
    response = client.describe_images(**ec2.requests.describe_images[distribution])
    images = response["Images"]
    images.sort(key=lambda image: image["CreationDate"], reverse=True)
    latest = images[0]
    return latest["ImageId"]
