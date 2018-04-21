import boto3

describe_images_requests_map = {
    "ubuntu-xenial": {"Filters": [{"Name": "name",
                                   "Values": ["ubuntu/images/hvm-ssd/ubuntu-xenial-*"]}],
                      "Owners": ["099720109477"]}
}

ec2_client = boto3.client("ec2")


def latest_image(distribution):
    return ec2_client.describe_images(**describe_images_requests_map[distribution])
