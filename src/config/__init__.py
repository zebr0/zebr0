import configparser

import requests

parser = configparser.ConfigParser()
parser.read(["/etc/zebr0.conf", "zebr0.conf"])

base_url = parser.get("config", "base_url", fallback="https://raw.githubusercontent.com/zebr0/zebr0-files/master")


def fetch_distribution(project: str) -> str:
    return _fetch(project, "distribution", default="ubuntu-bionic")


def fetch_instance_type(project: str, stage: str) -> str:
    return _fetch(project, stage, "instance-type", default="t2.micro")


def _fetch(*args, default: str) -> str:
    key = "/".join(args)
    response = requests.get(base_url + "/" + key)
    if response.ok:
        return response.text.strip()
    else:
        print("missing key:", key)
        return default
