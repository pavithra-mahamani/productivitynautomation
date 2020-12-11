import sys
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster, ClusterOptions
import requests
import argparse
import uuid
import logging

logger = logging.getLogger("move_from_dynamic_to_static")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

ap = argparse.ArgumentParser()

ap.add_argument("-o", "--os", required=True, type=str, help="Operating system")
ap.add_argument("-c", "--count", type=int, default=1, help="Number of VMs")
ap.add_argument("-p", "--pools", required=True, help="List of static pools, only 1 if removing")
ap.add_argument("--cb_dynamic", default="172.23.104.180", help="CB server for dynamic pool")
ap.add_argument("--cb_static", default="172.23.121.84", help="CB server for static pool")
ap.add_argument("--cb_username", default="Administrator")
ap.add_argument("--cb_password", default="password")
ap.add_argument("--dynvmservice", default="172.23.104.180:5000", help="Dynamic VM service url")
ap.add_argument("-a", "--action", choices=("add", "remove"), default="add")

args = vars(ap.parse_args())

args["pools"] = args["pools"].split(",")

if args["count"] <= 0:
    logger.error("count must be > 0")
    sys.exit(1)

logger.info(args)

cb_dynamic = Cluster('couchbase://' + args["cb_dynamic"], ClusterOptions(PasswordAuthenticator(args["cb_username"], args["cb_password"])))
cb_static = Cluster('couchbase://' + args["cb_static"], ClusterOptions(PasswordAuthenticator(args["cb_username"], args["cb_password"])))

if args["action"] == "add":

    vm_name = str(uuid.uuid4())

    logger.debug("vms created with prefix name " + vm_name)

    # allocate vms
    res = list(requests.get("http://{}/getservers/{}?os={}&count={}".format(args["dynvmservice"], vm_name, args["os"], args["count"])).json())

    for ip in res:
        # get necessary details to add to static pool bucket
        details = list(cb_dynamic.query("select origin, memory, os_version from `QE-dynserver-pool` where ipaddr = '{}'".format(ip)))[0]

        docValue = {}
        docValue["ipaddr"] = ip
        docValue["origin"] = details["origin"]
        docValue["os"] = args["os"]
        docValue["state"] = "available"
        docValue["poolId"] = args["pools"]
        docValue["prevUser"] = ""
        docValue["username"] = ""
        docValue["ver"] = "12"
        docValue["memory"] = details["memory"]
        docValue["os_version"] = details["os_version"]

        cb_static.bucket("QE-server-pool").insert(ip, docValue)

        logger.info("{} added to static pools: {}".format(ip, ",".join(args["pools"])))

elif args["action"] == "remove":
    # TODO: Remove from multiple pools
    if len(args["pools"]) != 1:
        logger.error("1 pool required when removing")
        sys.exit(1)

    pool_id = args["pools"][0]

    # get all active dynamic vm ips
    info = requests.get("http://{}/showall".format(args["dynvmservice"])).json()
    ips = {}
    for xhost in info.values():
        for vm in xhost:
            ip = vm["networkinfo"].split(",")[0]
            ips[ip] = vm["name"]

    # get all dyanmic where ip in list of ips, state is available and poolId = pool_id or pool_id in poolId

    ips_to_remove = list(cb_static.query("select raw META().id from `QE-server-pool` where ipaddr in {0} and state = 'available' and (poolId = '{1}' or '{1}' in poolId)".format(list(ips.keys()), pool_id)))

    logger.info("ips to remove: {}".format(",".join(ips_to_remove)))

    removed_count = 0

    for ip in ips_to_remove:
        res = requests.get("http://{}/releaseservers/{}".format(args["dynvmservice"], ips[ip])).json()

        # vm wasn't deleted
        if res != [ips[ip]]:
            continue

        cb_static.bucket("QE-server-pool").remove(ip)        

        logger.info("{} removed from static pool: {}".format(ip, pool_id))

        removed_count += 1

        if removed_count == args["count"]:
            break
        
    logger.info("removed {} vms from static pool: {}".format(removed_count, pool_id))
