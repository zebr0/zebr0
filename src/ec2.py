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


def init_environment(project: str, stage: str):
    create_vpc_if_needed(project, stage)
    create_instance_if_needed(project, stage)


def create_vpc_if_needed(project, stage):
    request = {"Filters": [{"Name": "tag:project", "Values": [project]},
                           {"Name": "tag:stage", "Values": [stage]}]}
    response = client.describe_vpcs(**request)
    pprint.pprint(response)

    if not response.get("Vpcs"):
        request = {
            "CidrBlock": config.fetch_network_cidr(project, stage)
        }
        response = client.create_vpc(**request)
        pprint.pprint(response)

        request = {
            "Resources": [response.get("Vpc").get("VpcId")],
            "Tags": [{"Key": "project", "Value": project},
                     {"Key": "stage", "Value": stage}]
        }
        response = client.create_tags(**request)
        pprint.pprint(response)


def create_instance_if_needed(project, stage):
    request = {"Filters": [{"Name": "tag:project", "Values": [project]},
                           {"Name": "tag:stage", "Values": [stage]},
                           {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]}
    response = client.describe_instances(**request)
    pprint.pprint(response)

    if not response.get("Reservations"):
        request = {
            "ImageId": fetch_latest_image_id(config.fetch_distribution(project)),
            "MinCount": 1,
            "MaxCount": 1,
            "KeyName": "keypair",
            "InstanceType": config.fetch_instance_type(project, stage)
        }
        response = client.run_instances(**request)
        pprint.pprint(response)

        request = {
            "Resources": [response.get("Instances")[0].get("InstanceId")],
            "Tags": [{"Key": "project", "Value": project},
                     {"Key": "stage", "Value": stage}]
        }
        response = client.create_tags(**request)
        pprint.pprint(response)
