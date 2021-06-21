from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
import logging
import json
from flask import Flask, Response
from csv import DictReader
import requests

log = logging.getLogger("exporter")
logging.basicConfig(
    format='[%(asctime)s][%(levelname)s] %(message)s', level=logging.DEBUG)

with open("queries.json") as json_file:
    settings = json.load(json_file)

log.info("Loaded queries.json")

csvs = settings.get("csvs") or {}


app = Flask(__name__)

for options in settings['queries'] + settings["columns"]:
    log.info("Registered metrics collection for {}".format(options['name']))


def get_labels(row, options):
    rename_map = options.get("rename", {})
    return ["{}=\"{}\"".format(rename_map[label] if label in rename_map else label, row[label]) for label in options["labels"]]


def collect_cb(clusters, metrics, options):
    rows = clusters[options["cluster"]].query(options["query"]).rows()
    for row in rows:
        if len(options["labels"]) > 0:
            labels = get_labels(row, options)
            metrics.append("{}{{{}}} {}".format(
                options["name"], ",".join(labels), row[options["value_key"]]))
        else:
            metrics.append("{} {}".format(
                options["name"], row[options["value_key"]]))


def collect_csv(metrics, options):
    csvfile = requests.get(csvs[options["csv"]]).text.splitlines()
    reader = DictReader(csvfile)
    for row in reader:
        if options["column"] not in row or row[options["column"]] == "":
            continue
        if len(options["labels"]) > 0:
            labels = get_labels(row, options)
            metrics.append("{}{{{}}} {}".format(
                options["name"], ",".join(labels), row[options["column"]]))
        else:
            metrics.append("{} {}".format(
                options["name"], row[options["column"]]))


@app.route("/metrics")
def metrics():
    metrics = []
    clusters = {}
    for [cluster_name, options] in settings['clusters'].items():
        if cluster_name not in clusters:
            try:
                clusters[cluster_name] = Cluster('couchbase://'+options['host'],
                                                ClusterOptions(
                    PasswordAuthenticator(options['username'], options['password'])))
            except Exception as e:
                log.warning("Couldn't connect to cluster {}".format(e))
            log.debug("Connected to {}".format(options['host']))
    for options in settings["queries"] + settings["columns"]:
        log.debug("Collecting metrics for {}".format(options["name"]))
        try:
            if "cluster" in options:
                collect_cb(clusters, metrics, options)
            elif "csv" in options:
                collect_csv(metrics, options)
            else:
                raise Exception("Invalid type")
        except Exception as e:
            log.warning("Error while collecting {}: {}".format(
                options["name"], e))
    return Response("\n".join(metrics), mimetype="text/plain")


if __name__ == "__main__":
    log.info("Started HTTP server on port 8000")
    app.run(host="0.0.0.0", port=8000)
