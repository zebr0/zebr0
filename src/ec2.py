import boto3

import config

client = boto3.client("ec2")


def describe_vpc(project, stage):
    print("checking vpc")

    vpcs = client.describe_vpcs(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]}]
    ).get("Vpcs")

    return vpcs[0] if vpcs else None


def describe_subnet(project, stage):
    print("checking subnet")

    subnets = client.describe_subnets(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]}]
    ).get("Subnets")

    return subnets[0] if subnets else None


def describe_instance(project, stage):
    print("checking instance")

    reservations = client.describe_instances(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]},
                 {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
    ).get("Reservations")

    return reservations[0].get("Instances")[0] if reservations else None


def init_environment(args):
    vpc_id = create_vpc_if_needed(args.project, args.stage)
    subnet_id = create_subnet_if_needed(args.project, args.stage, vpc_id)
    instance_id = create_instance_if_needed(args.project, args.stage, subnet_id)


def create_vpc_if_needed(project, stage):
    vpc = describe_vpc(project, stage)

    if not vpc:
        print("vpc not found, creating vpc")
        network_cidr = config.fetch_network_cidr(project, stage)
        create_vpc = client.create_vpc(CidrBlock=network_cidr)
        vpc_id = create_vpc.get("Vpc").get("VpcId")
        client.get_waiter('vpc_exists').wait(VpcIds=[vpc_id])
        create_tags(project, stage, vpc_id)
        return vpc_id
    else:
        return vpc.get("VpcId")


def create_subnet_if_needed(project, stage, vpc_id):
    subnet = describe_subnet(project, stage)

    if not subnet:
        print("subnet not found, creating subnet")
        network_cidr = config.fetch_network_cidr(project, stage)
        create_subnet = client.create_subnet(CidrBlock=network_cidr, VpcId=vpc_id)
        subnet_id = create_subnet.get("Subnet").get("SubnetId")
        create_tags(project, stage, subnet_id)
        return subnet_id
    else:
        return subnet.get("SubnetId")


def create_instance_if_needed(project, stage, subnet_id):
    instance = describe_instance(project, stage)

    if not instance:
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
        return instance.get("InstanceId")


def create_tags(project, stage, resource_id):
    print("updating tags")
    client.create_tags(
        Resources=[resource_id],
        Tags=[{"Key": "project", "Value": project},
              {"Key": "stage", "Value": stage}]
    )


def fetch_latest_image_id(distribution):
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
    destroy_instance_if_needed(args.project, args.stage)
    destroy_subnet_if_needed(args.project, args.stage)
    destroy_vpc_if_needed(args.project, args.stage)


def destroy_instance_if_needed(project, stage):
    instance = describe_instance(project, stage)
    if instance:
        print("instance found, destroying instance")
        instance_ids = {"InstanceIds": [instance.get("InstanceId")]}
        client.terminate_instances(**instance_ids)
        client.get_waiter('instance_terminated').wait(**instance_ids)


def destroy_subnet_if_needed(project, stage):
    subnet = describe_subnet(project, stage)
    if subnet:
        print("subnet found, destroying subnet")
        client.delete_subnet(SubnetId=subnet.get("SubnetId"))


def destroy_vpc_if_needed(project, stage):
    vpc = describe_vpc(project, stage)
    if vpc:
        print("vpc found, destroying vpc")
        client.delete_vpc(VpcId=vpc.get("VpcId"))
