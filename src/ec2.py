import json

import boto3

import config

client = boto3.client(service_name="ec2", region_name="eu-central-1")  # TODO


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


def describe_internet_gateway(project, stage):
    print("checking internet gateway")

    internet_gateways = client.describe_internet_gateways(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]}]
    ).get("InternetGateways")

    return internet_gateways[0] if internet_gateways else None


def describe_address(project, stage):
    print("checking address")

    addresses = client.describe_addresses(
        Filters=[{"Name": "tag:project", "Values": [project]},
                 {"Name": "tag:stage", "Values": [stage]}]
    ).get("Addresses")

    return addresses[0] if addresses else None


def create_vpc_if_needed(project, stage):
    vpc = describe_vpc(project, stage)

    if not vpc:
        print("vpc not found, creating vpc")
        network_cidr = config.lookup(project, stage, "network-cidr")
        create_vpc = client.create_vpc(CidrBlock=network_cidr)
        vpc_id = create_vpc.get("Vpc").get("VpcId")
        client.get_waiter("vpc_exists").wait(VpcIds=[vpc_id])
        create_tags(project, stage, vpc_id)

        security_groups = client.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("SecurityGroups")
        client.authorize_security_group_ingress(
            GroupId=security_groups[0].get("GroupId"),
            IpPermissions=[
                {"FromPort": 80, "ToPort": 80, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": -1, "ToPort": -1, "IpProtocol": "icmp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}  # TODO
            ]
        )

        return vpc_id
    else:
        return vpc.get("VpcId")


def create_subnet_if_needed(project, stage, vpc_id):
    subnet = describe_subnet(project, stage)

    if not subnet:
        print("subnet not found, creating subnet")
        network_cidr = config.lookup(project, stage, "network-cidr")
        create_subnet = client.create_subnet(CidrBlock=network_cidr, VpcId=vpc_id)
        subnet_id = create_subnet.get("Subnet").get("SubnetId")
        create_tags(project, stage, subnet_id)
        return subnet_id
    else:
        return subnet.get("SubnetId")


def create_internet_gateway_if_needed(project, stage, vpc_id):
    internet_gateway = describe_internet_gateway(project, stage)

    if not internet_gateway:
        print("internet gateway not found, creating internet gateway")
        internet_gateway_id = client.create_internet_gateway().get("InternetGateway").get("InternetGatewayId")
        create_tags(project, stage, internet_gateway_id)
        client.attach_internet_gateway(InternetGatewayId=internet_gateway_id, VpcId=vpc_id)

        route_tables = client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("RouteTables")
        client.create_route(DestinationCidrBlock="0.0.0.0/0", GatewayId=internet_gateway_id, RouteTableId=route_tables[0].get("RouteTableId"))


def create_instance_if_needed(project, stage, subnet_id):
    instance = describe_instance(project, stage)

    if not instance:
        print("instance not found, creating instance")
        run_instances = client.run_instances(
            ImageId=lookup_latest_image_id(project, stage),
            MinCount=1,
            MaxCount=1,
            KeyName="keypair",  # TODO
            InstanceType=config.lookup(project, stage, "instance-type"),
            SubnetId=subnet_id
        )
        instance_id = run_instances.get("Instances")[0].get("InstanceId")
        client.get_waiter("instance_running").wait(InstanceIds=[instance_id])
        create_tags(project, stage, instance_id)
        return instance_id
    else:
        return instance.get("InstanceId")


def create_address_if_needed(project, stage, instance_id):
    address = describe_address(project, stage)

    if not address:
        print("address not found, creating address")
        allocate_address = client.allocate_address()
        allocation_id = allocate_address.get("AllocationId")
        create_tags(project, stage, allocation_id)
        client.associate_address(AllocationId=allocation_id, InstanceId=instance_id)
        return allocate_address.get("PublicIp")
    else:
        return address.get("PublicIp")


def create_tags(project, stage, resource_id):
    print("updating tags")
    client.create_tags(
        Resources=[resource_id],
        Tags=[{"Key": "project", "Value": project},
              {"Key": "stage", "Value": stage}]
    )


def lookup_latest_image_id(project, stage):
    response = client.describe_images(**json.loads(config.lookup(project, stage, "image")))
    images = response.get("Images")
    images.sort(key=lambda image: image.get("CreationDate"), reverse=True)
    latest = images[0]
    return latest.get("ImageId")


def destroy_address_if_needed(project, stage):
    address = describe_address(project, stage)
    if address:
        print("address found, destroying address")
        client.disassociate_address(AssociationId=address.get("AssociationId"))
        client.release_address(AllocationId=address.get("AllocationId"))


def destroy_instance_if_needed(project, stage):
    instance = describe_instance(project, stage)
    if instance:
        print("instance found, destroying instance")
        instance_ids = {"InstanceIds": [instance.get("InstanceId")]}
        client.terminate_instances(**instance_ids)
        client.get_waiter("instance_terminated").wait(**instance_ids)


def destroy_internet_gateway_if_needed(project, stage):
    internet_gateway = describe_internet_gateway(project, stage)
    if internet_gateway:
        print("internet gateway found, destroying internet gateway")
        internet_gateway_id = internet_gateway.get("InternetGatewayId")
        client.detach_internet_gateway(
            InternetGatewayId=internet_gateway_id,
            VpcId=internet_gateway.get("Attachments")[0].get("VpcId")
        )
        client.delete_internet_gateway(InternetGatewayId=internet_gateway_id)


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
