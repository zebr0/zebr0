import pprint

import boto3

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


def run_instance():
    request = {
        "ImageId": fetch_latest_image_id("ubuntu-bionic"),
        "MinCount": 1,
        "MaxCount": 1,
        "KeyName": "keypair",
        "InstanceType": "t2.micro"
    }

    response = client.run_instances(**request)
    pprint.pprint(response)
