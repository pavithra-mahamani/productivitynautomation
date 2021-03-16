'''
Usage:

python missing.py <list of version strings>

Examples:

python missing.py 7.0.0-3874
python missing.py 7.0.0
python missing.py 7.0.0,6.6.1

'''

from datetime import timedelta
from couchbase.cluster import Cluster, ClusterOptions, ClusterTimeoutOptions
from couchbase.auth import PasswordAuthenticator
import traceback
from couchbase.collection import ReplaceOptions
from couchbase.exceptions import CASMismatchException, DocumentExistsException
import logging
import argparse

logger = logging.getLogger("missing")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

ap = argparse.ArgumentParser()

ap.add_argument("--cb_server", default="172.23.121.84")
ap.add_argument("--cb_username", default="Administrator")
ap.add_argument("--cb_password", default="password")
ap.add_argument("--update", default=False, action="store_true")
ap.add_argument("versions")

args = vars(ap.parse_args())

cluster = Cluster("couchbase://" + args["cb_server"], ClusterOptions(PasswordAuthenticator(
    args["cb_username"], args["cb_password"]), timeout_options=ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))))

server_bucket = cluster.bucket("server")
greenboard_bucket = cluster.bucket("greenboard")
greenboard_collection = greenboard_bucket.default_collection()
server_collection = server_bucket.default_collection()

supplied_versions = args["versions"].split(",")
versions = set()

for v in supplied_versions:
    for version in list(server_bucket.query("select raw `build` from server where `build` like '%{}%' group by `build`".format(v))):
        versions.add(version)

for version in sorted(versions, reverse=True):
    doc_id = "{}_server".format(version)
    doc = greenboard_collection.get(doc_id)
    greenboard = doc.content_as[dict]
    logger.info("searching for missing jobs in {}".format(version))
    for row in server_bucket.query("select META().id, os, build_id, component, name from server where `build` = '{}'".format(version)):
        update = False
        try:
            runs = greenboard["os"][row["os"]][row["component"]][row["name"]]
            found_build_id = False
            for run in runs:
                if run["build_id"] >= row["build_id"]:
                    found_build_id = True
            if not found_build_id:
                update = True
        except KeyError:
            update = True
        if update:
            logger.info(row["name"])
            if args["update"]:
                try:
                    doc = server_collection.get(row["id"])
                    cas = doc.cas
                    job = doc.content_as[dict]
                    server_collection.replace(
                        row["id"], job, ReplaceOptions(cas=cas))
                except Exception:
                    traceback.print_exc()
