import configparser
import logging
import subprocess

import requests

# TODO extract into its own library

default_filename = "zebr0.conf"
default_path = "/etc/" + default_filename

parser = configparser.ConfigParser()
parser.read([default_path, default_filename])

base_url = parser.get("config", "base_url", fallback="https://raw.githubusercontent.com/zebr0/zebr0-config/master")


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

        self.logger = logging.getLogger("zebr0.config.service")
        self.cache = {}

        self.logger.info("base_url: %s", base_url)
        self.logger.info("project: %s", project)
        self.logger.info("stage: %s", stage)

    def lookup(self, key):
        if not self.cache.get(key):
            self.cache[key] = self.remote_lookup(key)
        return self.cache.get(key)

    def remote_lookup(self, key):
        self.logger.info("looking for key '%s' in remote repository", key)

        for path in [[base_url, self.project, self.stage, key],
                     [base_url, self.project, key],
                     [base_url, key]]:
            response = requests.get("/".join(path))
            if response.ok:
                return response.text.strip()

        raise LookupError("key '{}' not found anywhere for project '{}', stage '{}' in '{}'".format(key, self.project, self.stage, base_url))
