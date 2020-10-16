from flask import Flask, request
from flask.json import jsonify

from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.options import LockMode

from threading import Thread, Lock
import time
import requests
import sys
import json
import csv

TARGETS_FILE = "targets.json"

app = Flask(__name__)

app.config['ENV'] = 'development'

cache_lock = Lock()
cache = {}

# Load stored targets on startup
targets_lock = Lock()
try:
    with open(TARGETS_FILE) as json_file:
        targets = json.load(json_file)
except Exception:
    targets = {}
    with open(TARGETS_FILE, 'w') as outfile:
        json.dump(targets, outfile)


clusters_lock = Lock()
clusters = {}  # cluster by host

if len(sys.argv) > 1:
    grafana_connection_string = sys.argv[1]


def add_cluster(host: str, username: str, password: str):
    clusters_lock.acquire()
    if host not in clusters:
        clusters[host] = Cluster('couchbase://' + host,
                                 ClusterOptions(
                                     PasswordAuthenticator(username, password)),
                                 lockmode=LockMode.WAIT)
    clusters_lock.release()


# add any couchbase clusters on startup
for target in targets.values():
    if target['source'] == "couchbase":
        host = target['host']
        username = target['username']
        password = target['password']
        add_cluster(host, username, password)


class UpdateThread(Thread):
    _terminate = False

    def terminate(self):
        self._terminate = True

    def run(self):
        """
        UpdateThread periodically refreshes data based on the refresh value specified by the user
        """
        while True:
            time.sleep(1)

            if self._terminate:
                return

            now = time.time()

            # calculating data can be quite slow if there's an expensive couchbase query or large json document
            # so that the cache lock is only held for a short period of time, separate the function that determines
            # which targets need to be updated from the calculating of the data for that target

            to_update = []

            cache_lock.acquire()
            targets_lock.acquire()

            for [target_name, target] in targets.items():

                if target_name not in cache:
                    continue

                if "refresh" in target:
                    refresh = target['refresh']
                else:
                    refresh = 60

                if now >= cache[target_name]['last_update'] + refresh:

                    to_update.append({
                        "type": target['type'],
                        "target": target_name
                    })

            targets_lock.release()
            cache_lock.release()

            for update in to_update:
                data_type = update['type']
                target = update['target']

                print("refreshing cache: " + target)

                try:
                    if data_type == "timeseries":
                        datapoints = calculate_datapoints(target)
                    elif data_type == "table":
                        datapoints = calculate_rows_and_columns(target)
                except Exception as e:
                    print("couldn't refresh cache: " +
                          target_name + " (" + str(e) + ")")
                    continue
                if data_type == "timeseries":
                    cache_datapoints(target, datapoints)
                elif data_type == "table":
                    cache_table(target, datapoints)

                print("refreshed cache: " + target)


@app.route("/add", methods=["POST"])
def add():
    """
    /add creates a new dashboard in grafana and returns the dashboard URL if it was created successfully
    """
    try:

        req = request.json
        data = req['data']
        grafana = req['grafana']

        panels = []

        # store any new targets
        for target in data:

            cache_lock.acquire()
            targets_lock.acquire()

            if target['name'] in cache:
                cache.pop(target['name'])

            targets[target['name']] = target

            with open(TARGETS_FILE, 'w') as outfile:
                json.dump(targets, outfile)

            targets_lock.release()
            cache_lock.release()

            if target['source'] == "couchbase":
                add_cluster(target['host'],
                            target['username'], target['password'])

        for panel_options in grafana:
            # targets for this panel, might already have been added
            panel_targets = []
            if "targets" in panel_options:
                for t in panel_options['targets']:
                    target = targets[t]
                    panel_targets.append({
                        "data": "", "refId": target['name'], "target": target['name'], "type": target['type']
                    })

            panel = {
                "datasource": "JSON",
                "title": panel_options['title'],
                "targets": panel_targets,
                "type": panel_options['type'],
                "gridPos": panel_options['grid_position'],
                "fieldConfig": {
                    "defaults": {},
                }
            }

            if "relative_time" in panel_options:
                panel['timeFrom'] = panel_options['relative_time']

            if panel_options['type'] == "gauge":

                field_config = {}

                if "thresholds" in panel_options:
                    field_config['thresholds'] = panel_options['thresholds']

                if "max" in panel_options:
                    field_config['max'] = panel_options['max']

                panel['fieldConfig']['defaults'] = field_config

            if panel_options['type'] == "gauge" or panel_options['type'] == "stat":
                if "calculation" in panel_options:
                    panel['options'] = {
                        "reduceOptions": {
                            "calcs": [panel_options['calculation']]
                        },
                        "graphMode": "none",
                    }

            if "overrides" in panel_options:
                overrides = []

                for [name, override_options] in panel_options['overrides'].items():
                    properties = []

                    for [override_name, override] in override_options.items():
                        properties.append({
                            "id": override_name,
                            "value": override
                        })

                    overrides.append({
                        "matcher": {
                            "id": "byName",
                            "options": name,
                        },
                        "properties": properties
                    })

                panel['fieldConfig']['overrides'] = overrides

            if panel_options['type'] == "graph":
                if "stack" in panel_options:
                    panel['stack'] = panel_options['stack']

            if panel_options['type'] == "text":

                if "text" in panel_options:
                    panel['options'] = {
                        "mode": "markdown",
                        "content": panel_options['text'],
                    }

                if "links" in panel_options:
                    links = '<ul>'

                    for link in panel_options['links']:

                        links += '<li><a target="_blank" href="' + \
                            link['link'] + '">' + link['text'] + '</a></li>'

                    links += "</ul>"

                    panel['options'] = {
                        "mode": "html",
                        "content": links,
                    }

            panels.append(panel)

        if len(panels) == 0:
            return {
                "result": "data added"
            }

        res = {
            "dashboard": {
                "title": req['dashboard_title'],
                "refresh": "1m",
                "panels": panels
            },
            "overwrite": True
        }

        grafana_response = requests.post(
            grafana_connection_string + "/api/dashboards/db", json=res).json()

        if grafana_response['status'] == "success":
            return {
                'result': grafana_response['url'],
            }
        else:
            return {
                "error": grafana_response['message']
            }

    except Exception as e:
        return {"error": str(e)}, 500


@ app.route("/")
def status():
    """
    / responds with a 200 status as required by the Grafana JSON plugin
    """
    return {'status': 'ok'}


@ app.route("/search", methods=['POST'])
def search():
    """
    /search responds with all of the targets. This allows any data source added with the /add endpoint to show up in Grafana
    """
    targets_lock.acquire()
    ret = jsonify(list(targets.keys()))
    targets_lock.release()
    return ret


def calculate_rows_and_columns(target):
    """
    Returns data in a tabular format for Grafana.
    columns is a list of column names and types
    rows is a list of values for each column
    """

    target = targets[target]
    columns = target['columns']

    if target['source'] == "couchbase":
        cluster = clusters[target['host']]
        data = cluster.query(target['query']).rows()
        rows = [[row[column['text']] for column in columns] for row in data]
    elif target['source'] == "json":
        data = requests.get(target['file']).json()
        rows = [[row[column['text']] for column in columns] for row in data]
    elif target['source'] == "csv":
        data = requests.get(target['file']).text.splitlines()
        data = list(csv.reader(data))
        column_names = [column['text'] for column in columns]
        csv_columns = dict(enumerate(data[0])).items()
        selected_columns = [i for [i, col]
                            in csv_columns if col in column_names]
        rows = [[row[column] for column in selected_columns]
                for row in data[1:]]

    return {
        "columns": columns,
        "rows": rows,
        "type": "table"
    }


def calculate_datapoints(target: str):
    """
    Returns data in a timeseries format
    datapoints is formatted as a list of 2 item tuples in the format [value, timestamp]
    """

    target = targets[target]

    def calculate_group_by(data, group_by: str, value_key, timestamp_key):
        ret = {}
        for row in data:
            group_name = row[group_by]
            if group_name in ret:
                group = ret[group_name]
            else:
                ret[group_name] = {"target": group_name, "datapoints": []}
                group = ret[group_name]

            group['datapoints'].append(
                [int(row[value_key]), int(row[timestamp_key])])

        return list(ret.values())

    if target['source'] == "couchbase":
        cluster = clusters[target['host']]
        data = cluster.query(target['query']).rows()
        timestamp_key = target['timestamp_key']
        value_key = target['value_key']

        if "group_by" in target:
            return calculate_group_by(data, target['group_by'], value_key, timestamp_key)

        datapoints = [[row[value_key], row[timestamp_key]] for row in data]

    elif target['source'] == "json":
        timestamp_key = target['timestamp_key']
        value_key = target['value_key']
        data = requests.get(target['file']).json()

        if "group_by" in target:
            return calculate_group_by(data, target['group_by'], value_key, timestamp_key)

        datapoints = [[row[value_key], row[timestamp_key]] for row in data]

    elif target['source'] == "csv":
        timestamp_column = int(target['timestamp_column'])
        value_column = int(target['value_column'])
        data = requests.get(target['file']).text.splitlines()
        data = list(csv.reader(data))

        if "group_by" in target:
            return calculate_group_by(data[1:], target['group_by'], value_column, timestamp_column)

        datapoints = [[int(row[value_column]), int(row[timestamp_column])]
                      for row in data[1:]]

    return {
        "target": target['name'],
        "datapoints": datapoints
    }


def cache_datapoints(target: str, datapoints):
    cache_lock.acquire()
    cache[target] = {
        "datapoints": datapoints,
        "last_update": time.time(),
        "type": "timeseries"
    }
    cache_lock.release()


def cache_table(target: str, table):
    cache_lock.acquire()
    cache[target] = {
        "table": table,
        "last_update": time.time(),
        "type": "table"
    }
    cache_lock.release()


@ app.route("/query", methods=['POST'])
def query():
    """
    /query responds to a Grafana data request and is formatted as either datapoints for time series data 
    or rows and columns for tabular data
    """

    data = []

    try:

        for target in request.json['targets']:
            data_type = target['type']
            target = target['target']

            if data_type == "timeseries":
                cache_lock.acquire()
                if target in cache:
                    datapoints = cache[target]['datapoints']
                    cache_lock.release()
                else:
                    cache_lock.release()
                    datapoints = calculate_datapoints(target)
                    cache_datapoints(target, datapoints)

            elif data_type == "table":
                cache_lock.acquire()
                if target in cache:
                    datapoints = cache[target]['table']
                    cache_lock.release()
                else:
                    cache_lock.release()
                    datapoints = calculate_rows_and_columns(target)
                    cache_table(target, datapoints)

            # single input target can produce multiple output targets
            if isinstance(datapoints, list):
                data.extend(datapoints)
            else:
                data.append(datapoints)

        return jsonify(data)

    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":

    # show usage
    if len(sys.argv) == 1 or sys.argv[1] == "--help":
        print('Automated Grafana Dashboards\n')
        print(
            'USAGE: python dashboard.py [GRAFANA_URL] (e.g. http://admin:password@127.0.0.1:3000)')
    else:
        update_thread = UpdateThread()
        update_thread.start()
        app.run(host="0.0.0.0")
        update_thread.terminate()
        update_thread.join()
