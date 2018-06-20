import boto3

import config

client = boto3.client("route53")


def create_dns_entry_if_needed(project, stage, address):
    domain_name = config.fetch_domain_name()
    if domain_name:
        hosted_zones = client.list_hosted_zones_by_name(DNSName=domain_name).get("HostedZones")
        if hosted_zones:
            client.change_resource_record_sets(
                HostedZoneId=hosted_zones[0].get("Id"),
                ChangeBatch={"Changes": [{
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": ".".join([stage, project, domain_name]),  # TODO
                        "Type": "A",
                        "TTL": 300,  # TODO
                        "ResourceRecords": [{"Value": address}]
                    }
                }]}
            )
        else:
            pass
    else:
        pass
