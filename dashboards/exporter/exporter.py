from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY
import time
from prometheus_client import start_http_server, Counter, Gauge, Summary, Histogram
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.options import LockMode
import logging
import json

log = logging.getLogger("exporter")
logging.basicConfig(
    format='[%(asctime)s][%(levelname)s] %(message)s', level=logging.DEBUG)

with open("queries.json") as json_file:
    settings = json.load(json_file)

log.info("Loaded queries.json")

log.info("Connecting to clusters")

clusters = {}
for [cluster_name, options] in settings['clusters'].items():
    if cluster_name not in clusters:
        clusters[cluster_name] = Cluster('couchbase://'+options['host'],
                                         ClusterOptions(
            PasswordAuthenticator(options['username'], options['password'])),
            lockmode=LockMode.WAIT)
        log.info("Connected to %s", options['host'])

log.info("Connected to clusters")


class CouchbaseQueryCollector():
    def __init__(self, cluster, name, description, query, value_key, labels=[]):
        self.cluster = cluster
        self.query = query
        self.name = name
        self.description = description
        self.labels = labels
        self.value_key = value_key

    def collect(self):
        log.debug("Collecting metrics for %s", self.name)

        g = GaugeMetricFamily(
            self.name, self.description, labels=self.labels)

        try:
            rows = clusters[self.cluster].query(self.query).rows()

            for row in rows:
                g.add_metric([row[label]
                              for label in self.labels], row[self.value_key])

        except Exception as e:
            log.warn("Error while collecting %s: %s", self.name, e)
            pass

        yield g


for options in settings['queries']:

    REGISTRY.register(CouchbaseQueryCollector(
        options['cluster'], options['name'], options['description'], options['query'], options['value_key'], options['labels']))

    log.info("Registered metrics collection for %s", options['name'])


start_http_server(8000)

log.info("Started HTTP server on port 8000")

while True:
    time.sleep(1000)
