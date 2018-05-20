import pprint

import boto3

import config

client = boto3.client("ec2")


def fetch_latest_image_id(distribution: str) -> str:
    request = {
        "ubuntu-xenial": {"Filters": [{"Name": "name",
                                       "Values": ["ubuntu/images/hvm-ssd/ubuntu-xenial-*"]}],
                          "Owners": ["099720109477"]},
        "ubuntu-bionic": {"Filters": [{"Name": "name",
                                       "Values": ["ubuntu/images/hvm-ssd/ubuntu-bionic-*"]}],
                          "Owners": ["099720109477"]}
    }

    response = client.describe_images(**request.get(distribution))
    images = response.get("Images")
    images.sort(key=lambda image: image.get("CreationDate"), reverse=True)
    latest = images[0]
    return latest.get("ImageId")


def run_instance(project: str, stage: str):
    request = {
        "ImageId": fetch_latest_image_id(config.fetch_distribution(project)),
        "MinCount": 1,
        "MaxCount": 1,
        "KeyName": "keypair",
        "InstanceType": config.fetch_instance_type(project, stage)
    }

    response = client.run_instances(**request)
    pprint.pprint(response)
