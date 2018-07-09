import configparser
import subprocess

import requests

default_filename = "zebr0-aws.conf"
default_path = "/etc/" + default_filename

parser = configparser.ConfigParser()
parser.read([default_path, default_filename])

base_url = parser.get("config", "base_url", fallback="https://raw.githubusercontent.com/zebr0/zebr0-aws-config/master")


def edit_config(filename):
    parser["config"] = {
        "base_url": base_url
    }

    with open(filename, "w") as file:
        parser.write(file)
    subprocess.call(["/usr/bin/editor", filename])


class Service:
    def __init__(self, project, stage):
        self.project = project
        self.stage = stage

        self.cache = {}

    def lookup(self, key):
        if not self.cache.get(key):
            self.cache[key] = self.remote_lookup(key)
        return self.cache.get(key)

    def remote_lookup(self, key):
        for path in [[base_url, self.project, self.stage, key],
                     [base_url, self.project, key],
                     [base_url, key]]:
            response = requests.get("/".join(path))
            if response.ok:
                return response.text.strip()
        raise LookupError("key '{}' not found anywhere for project '{}', stage '{}' in '{}'".format(key, self.project, self.stage, base_url))
