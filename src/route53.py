import boto3

import config

domain_name_key = "domain-name"
client = boto3.client("route53")


def create_dns_entry_if_needed(project, stage, address):
    domain_name = config.fetch(domain_name_key)
    if not domain_name:
        print("missing configuration key '{}', skipping dns entry creation".format(domain_name_key))
        return

    hosted_zone_id = fetch_hosted_zone_id(domain_name)
    if not hosted_zone_id:
        return

    fqdn = fetch_fqdn(project, stage, domain_name)
    resource_record_set = fetch_resource_record_set(hosted_zone_id, fqdn)

    if not resource_record_set:
        client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Changes": [{
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": fqdn,
                    "Type": "A",
                    "TTL": 300,  # TODO
                    "ResourceRecords": [{"Value": address}]
                }
            }]}
        )


def destroy_dns_entry_if_needed(project, stage):
    domain_name = config.fetch(domain_name_key)
    if not domain_name:
        return

    hosted_zone_id = fetch_hosted_zone_id(domain_name)
    if not hosted_zone_id:
        return

    fqdn = fetch_fqdn(project, stage, domain_name)
    resource_record_set = fetch_resource_record_set(hosted_zone_id, fqdn)

    if resource_record_set:
        client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Changes": [{
                "Action": "DELETE",
                "ResourceRecordSet": resource_record_set
            }]}
        )


def fetch_hosted_zone_id(domain_name):
    hosted_zones = client.list_hosted_zones_by_name(DNSName=domain_name, MaxItems="1").get("HostedZones")
    if hosted_zones and hosted_zones[0].get("Name") == domain_name:
        return hosted_zones[0].get("Id")
    else:
        print("no hosted zone was found in route53 for the '{}' domain, it needs to be created manually".format(domain_name))


def fetch_fqdn(project, stage, domain_name):
    return ".".join([stage, project, domain_name])  # TODO


def fetch_resource_record_set(hosted_zone_id, fqdn):
    resource_record_sets = client.list_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        StartRecordName=fqdn,
        StartRecordType="A",
        MaxItems="1"
    ).get("ResourceRecordSets")

    return resource_record_sets[0] if resource_record_sets and resource_record_sets[0].get("Name") == fqdn else None
