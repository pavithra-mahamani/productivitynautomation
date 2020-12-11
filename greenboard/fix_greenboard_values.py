'''
Usage:

python fix_greenboard_values.py <list of version strings>

Examples:

python fix_greenboard_values.py 7.0.0-3874
python fix_greenboard_values.py 7.0.0
python fix_greenboard_values.py 7.0.0,6.6.1

'''

from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
import traceback
from couchbase.collection import ReplaceOptions
from couchbase.exceptions import CASMismatchException, DocumentExistsException
import logging
import argparse

logger = logging.getLogger("fix_greenboard_values")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

ap = argparse.ArgumentParser()

ap.add_argument("--cb_server", default="172.23.121.84")
ap.add_argument("--cb_username", default="Administrator")
ap.add_argument("--cb_password", default="password")
ap.add_argument("versions")

args = vars(ap.parse_args())

cluster = Cluster("couchbase://" + args["cb_server"], ClusterOptions(PasswordAuthenticator(args["cb_username"], args["cb_password"])))

server_bucket = cluster.bucket("server")
greenboard_bucket = cluster.bucket("greenboard")
greenboard_collection = greenboard_bucket.default_collection()

supplied_versions = args["versions"].split(",")
versions = set()

for v in supplied_versions:
    for version in list(server_bucket.query("select raw `build` from server where `build` like '%{}%' group by `build`".format(v))):
        versions.add(version)

for version in versions:
    logger.info("fixing {}".format(version))
    try:
        while True:
            doc_id = "{}_server".format(version)

            doc = greenboard_collection.get(doc_id)
            cas = doc.cas
            greenboard = doc.content_as[dict]

            updated = False

            for row in server_bucket.query("select build_id, os, component, name, duration, totalCount, failCount, result from server where `build` = '{}'".format(version)):
                try:
                    all_runs = greenboard["os"][row["os"]][row["component"]][row["name"]]

                    keys_to_check = ["duration", "failCount", "result", "totalCount"]

                    for run in all_runs:
                        if row["build_id"] == run["build_id"]:
                            for key in keys_to_check:
                                if key in row and key in run and row[key] != run[key]:
                                    logger.info("corrected {} from {} to {} for {} in {}".format(key, run[key], row[key], row["name"], version))
                                    run[key] = row[key]
                                    updated = True

                except Exception:
                    continue

            if updated:
                total_count = 0
                fail_count = 0

                for os in greenboard["os"]:
                    for component in greenboard["os"][os]:
                        for job in greenboard["os"][os][component]:
                            if len(greenboard["os"][os][component][job]) > 0:
                                older_build = greenboard['os'][os][component][job][0]
                                total_count += older_build['totalCount']
                                fail_count += older_build['failCount']


                greenboard["totalCount"] = total_count
                greenboard["failCount"] = fail_count

                try:
                    greenboard_collection.replace(doc_id, greenboard, ReplaceOptions(cas=cas))
                    break
                except (CASMismatchException, DocumentExistsException):
                    continue
                except Exception:
                    traceback.print_exc()

            else:
                break

    except Exception:
        traceback.print_exc()