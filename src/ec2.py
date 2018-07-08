import json

import boto3


class Service:
    def __init__(self, config_service):
        self.config_service = config_service

        self.client = boto3.client(service_name="ec2", region_name="eu-central-1")  # TODO
        self.default_filters = [{"Name": "tag:project", "Values": [self.config_service.project]},
                                {"Name": "tag:stage", "Values": [self.config_service.stage]}]

    def describe_vpc(self):
        print("checking vpc")
        vpcs = self.client.describe_vpcs(Filters=self.default_filters).get("Vpcs")
        return vpcs[0] if vpcs else None

    def describe_subnet(self):
        print("checking subnet")
        subnets = self.client.describe_subnets(Filters=self.default_filters).get("Subnets")
        return subnets[0] if subnets else None

    def describe_instance(self):
        print("checking instance")
        filters = self.default_filters + [{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
        reservations = self.client.describe_instances(Filters=filters).get("Reservations")
        return reservations[0].get("Instances")[0] if reservations else None

    def describe_internet_gateway(self):
        print("checking internet gateway")
        internet_gateways = self.client.describe_internet_gateways(Filters=self.default_filters).get("InternetGateways")
        return internet_gateways[0] if internet_gateways else None

    def describe_address(self):
        print("checking address")
        addresses = self.client.describe_addresses(Filters=self.default_filters).get("Addresses")
        return addresses[0] if addresses else None

    def create_tags(self, resource_id):
        print("updating tags")
        self.client.create_tags(Resources=[resource_id], Tags=[{"Key": "project", "Value": self.config_service.project},
                                                               {"Key": "stage", "Value": self.config_service.stage}])

    def create_vpc_if_needed(self):
        vpc = self.describe_vpc()

        if not vpc:
            print("vpc not found, creating vpc")
            network_cidr = self.config_service.lookup("network-cidr")
            create_vpc = self.client.create_vpc(CidrBlock=network_cidr)
            vpc_id = create_vpc.get("Vpc").get("VpcId")
            self.client.get_waiter("vpc_exists").wait(VpcIds=[vpc_id])
            self.create_tags(vpc_id)

            security_groups = self.client.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("SecurityGroups")
            self.client.authorize_security_group_ingress(
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

    def create_subnet_if_needed(self, vpc_id):
        subnet = self.describe_subnet()

        if not subnet:
            print("subnet not found, creating subnet")
            network_cidr = self.config_service.lookup("network-cidr")
            create_subnet = self.client.create_subnet(CidrBlock=network_cidr, VpcId=vpc_id)
            subnet_id = create_subnet.get("Subnet").get("SubnetId")
            self.create_tags(subnet_id)
            return subnet_id
        else:
            return subnet.get("SubnetId")

    def create_internet_gateway_if_needed(self, vpc_id):
        internet_gateway = self.describe_internet_gateway()

        if not internet_gateway:
            print("internet gateway not found, creating internet gateway")
            internet_gateway_id = self.client.create_internet_gateway().get("InternetGateway").get("InternetGatewayId")
            self.create_tags(internet_gateway_id)
            self.client.attach_internet_gateway(InternetGatewayId=internet_gateway_id, VpcId=vpc_id)

            route_tables = self.client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("RouteTables")
            self.client.create_route(DestinationCidrBlock="0.0.0.0/0", GatewayId=internet_gateway_id, RouteTableId=route_tables[0].get("RouteTableId"))

    def lookup_latest_image_id(self):
        response = self.client.describe_images(**json.loads(self.config_service.lookup("image")))
        images = response.get("Images")
        images.sort(key=lambda image: image.get("CreationDate"), reverse=True)
        latest = images[0]
        return latest.get("ImageId")

    def create_instance_if_needed(self, subnet_id):
        instance = self.describe_instance()

        if not instance:
            print("instance not found, creating instance")
            run_instances = self.client.run_instances(
                ImageId=self.lookup_latest_image_id(),
                MinCount=1,
                MaxCount=1,
                KeyName="keypair",  # TODO
                InstanceType=self.config_service.lookup("instance-type"),
                SubnetId=subnet_id
            )
            instance_id = run_instances.get("Instances")[0].get("InstanceId")
            self.client.get_waiter("instance_running").wait(InstanceIds=[instance_id])
            self.create_tags(instance_id)
            return instance_id
        else:
            return instance.get("InstanceId")

    def create_address_if_needed(self, instance_id):
        address = self.describe_address()

        if not address:
            print("address not found, creating address")
            allocate_address = self.client.allocate_address()
            allocation_id = allocate_address.get("AllocationId")
            self.create_tags(allocation_id)
            self.client.associate_address(AllocationId=allocation_id, InstanceId=instance_id)
            return allocate_address.get("PublicIp")
        else:
            return address.get("PublicIp")

    def destroy_address_if_needed(self):
        address = self.describe_address()
        if address:
            print("address found, destroying address")
            self.client.disassociate_address(AssociationId=address.get("AssociationId"))
            self.client.release_address(AllocationId=address.get("AllocationId"))

    def destroy_instance_if_needed(self):
        instance = self.describe_instance()
        if instance:
            print("instance found, destroying instance")
            instance_ids = {"InstanceIds": [instance.get("InstanceId")]}
            self.client.terminate_instances(**instance_ids)
            self.client.get_waiter("instance_terminated").wait(**instance_ids)

    def destroy_internet_gateway_if_needed(self):
        internet_gateway = self.describe_internet_gateway()
        if internet_gateway:
            print("internet gateway found, destroying internet gateway")
            internet_gateway_id = internet_gateway.get("InternetGatewayId")
            self.client.detach_internet_gateway(
                InternetGatewayId=internet_gateway_id,
                VpcId=internet_gateway.get("Attachments")[0].get("VpcId")
            )
            self.client.delete_internet_gateway(InternetGatewayId=internet_gateway_id)

    def destroy_subnet_if_needed(self):
        subnet = self.describe_subnet()
        if subnet:
            print("subnet found, destroying subnet")
            self.client.delete_subnet(SubnetId=subnet.get("SubnetId"))

    def destroy_vpc_if_needed(self):
        vpc = self.describe_vpc()
        if vpc:
            print("vpc found, destroying vpc")
            self.client.delete_vpc(VpcId=vpc.get("VpcId"))
