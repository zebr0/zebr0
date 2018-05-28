import boto3

import config

client = boto3.client("ec2")


def init_environment(args):
    vpc_id = create_vpc_if_needed(args.project, args.stage)
    subnet_id = create_subnet_if_needed(args.project, args.stage, vpc_id)
    instance_id = create_instance_if_needed(args.project, args.stage, subnet_id)


def create_vpc_if_needed(project: str, stage: str) -> str:
    print("checking vpc")
    describe_vpcs = client.describe_vpcs(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]}]
    )

    if not describe_vpcs.get("Vpcs"):
        print("vpc not found, creating vpc")
        network_cidr = config.fetch_network_cidr(project, stage)
        create_vpc = client.create_vpc(CidrBlock=network_cidr)
        vpc_id = create_vpc.get("Vpc").get("VpcId")
        client.get_waiter('vpc_exists').wait(VpcIds=[vpc_id])
        create_tags(project, stage, vpc_id)
        return vpc_id
    else:
        return describe_vpcs.get("Vpcs")[0].get("VpcId")


def create_subnet_if_needed(project: str, stage: str, vpc_id: str) -> str:
    print("checking subnet")
    describe_subnets = client.describe_subnets(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]}]
    )

    if not describe_subnets.get("Subnets"):
        print("subnet not found, creating subnet")
        network_cidr = config.fetch_network_cidr(project, stage)
        create_subnet = client.create_subnet(CidrBlock=network_cidr, VpcId=vpc_id)
        subnet_id = create_subnet.get("Subnet").get("SubnetId")
        create_tags(project, stage, subnet_id)
        return subnet_id
    else:
        return describe_subnets.get("Subnets")[0].get("SubnetId")


def create_instance_if_needed(project: str, stage: str, subnet_id: str) -> str:
    print("checking instance")
    describe_instances = client.describe_instances(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]},
                 {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
    )

    if not describe_instances.get("Reservations"):
        print("instance not found, creating instance")
        run_instances = client.run_instances(
            ImageId=fetch_latest_image_id(config.fetch_distribution(project)),
            MinCount=1,
            MaxCount=1,
            KeyName="keypair",  # TODO
            InstanceType=config.fetch_instance_type(project, stage),
            SubnetId=subnet_id
        )
        instance_id = run_instances.get("Instances")[0].get("InstanceId")
        create_tags(project, stage, instance_id)
        return instance_id
    else:
        return describe_instances.get("Reservations")[0].get("Instances")[0].get("InstanceId")


def create_tags(project: str, stage: str, resource_id: str):
    print("updating tags")
    client.create_tags(
        Resources=[resource_id],
        Tags=[{"Key": "project", "Value": project},
              {"Key": "stage", "Value": stage}]
    )


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


def destroy_environment(args):
    pass
