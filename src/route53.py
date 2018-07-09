import boto3


class Service:
    def __init__(self, config_service):
        self.config_service = config_service
        self.resource_record_set = None

        try:
            self.domain_name = self.config_service.lookup("domain-name")
            self.client = boto3.client(service_name="route53", region_name=self.config_service.lookup("region"))

            hosted_zones = self.client.list_hosted_zones_by_name(DNSName=self.domain_name, MaxItems="1").get("HostedZones")
            if hosted_zones and hosted_zones[0].get("Name") == self.domain_name:
                self.hosted_zone_id = hosted_zones[0].get("Id")
                self.fqdn = ".".join([self.config_service.stage, self.config_service.project, self.domain_name])  # TODO

                print("checking resource record set")
                resource_record_sets = self.client.list_resource_record_sets(
                    HostedZoneId=self.hosted_zone_id,
                    StartRecordName=self.fqdn,
                    StartRecordType="A",
                    MaxItems="1"
                ).get("ResourceRecordSets")
                if resource_record_sets and resource_record_sets[0].get("Name") == self.fqdn:
                    self.resource_record_set = resource_record_sets[0]
            else:
                print("no hosted zone was found in route53 for the '{}' domain, it needs to be created manually".format(self.domain_name))
        except LookupError as error:
            print("{}, skipping dns entry management".format(error))

    def create_dns_entry_if_needed(self, address):
        if not self.resource_record_set:
            print("resource record set not found, creating resource record set")
            self.client.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch={"Changes": [{
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": self.fqdn,
                        "Type": "A",
                        "TTL": int(self.config_service.lookup("dns-record-ttl")),
                        "ResourceRecords": [{"Value": address}]
                    }
                }]}
            )

    def destroy_dns_entry_if_needed(self):
        if self.resource_record_set:
            print("resource record set found, destroying resource record set")
            self.client.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch={"Changes": [{
                    "Action": "DELETE",
                    "ResourceRecordSet": self.resource_record_set
                }]}
            )
