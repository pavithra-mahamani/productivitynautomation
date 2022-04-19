"""
    QE functional analysis:
    Extraction of the first run test esults forr the aborts and failed cases to see if any common infra issues with VMs/Xen Hosts. 

    Usage example: 
        python3 get_fresh_failed_list.py
        python3 get_fresh_failed_list.py 7.0.0-5071 ~/Downloads/qe_xen_hosts_info_summary.csv |tee  ~/Downloads/failed_5071.csv
"""
import sys
import os
import json
import urllib.request
from datetime import timedelta
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster, ClusterOptions, ClusterTimeoutOptions


def get_pool_data(servers):
    servers_list = []
    for server in servers.split(' '):
        servers_list.append(server)
    
    query = "SELECT ipaddr, os, state, origin, poolId FROM `QE-server-pool` WHERE ipaddr in ['" + "','".join(servers_list) + "']"
    pool_cb_host = os.environ.get('pool_cb_host')
    if not pool_cb_host:
        pool_cb_host = "172.23.104.162"
    pool_cb_user = os.environ.get('pool_cb_user')
    if not pool_cb_user:
        pool_cb_user = "Administrator"
    pool_cb_user_p = os.environ.get('pool_cb_password')
    if not cb_user_p:
        print("Error: pool_cb_password environment variable setting is missing!")
        exit(1)
    data = ''
    try:
        pool_cluster = Cluster("couchbase://"+pool_cb_host, ClusterOptions(PasswordAuthenticator(pool_cb_user, pool_cb_user_p),
        timeout_options=ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))))
        result = pool_cluster.query(query)
        for row in result:
            data += ("{}=({} {} {} {}) ".format(row['ipaddr'], row['state'], row['os'], row['poolId'], row['origin'])).replace(',',' ')
    except:
        print("exception:", sys.exc_info()[0])
    return data

if len(sys.argv) < 2:
    print("Usage: {} {}".format(sys.argv[0], "<cb_build> [xen_hosts_file] "))
    print("Environment: cb_password=, [cb_host=172.23.121.84, cb_user=Administrator, cb_bucket=greenboard]")
    exit(1)
cb_build = sys.argv[1]
xen_hosts_file = ''
if len(sys.argv) > 2:
    xen_hosts_file = sys.argv[2]
cb_host = os.environ.get('cb_host')
if not cb_host:
    cb_host = "172.23.121.84"
cb_user = os.environ.get('cb_user')
if not cb_user:
    cb_user = "Administrator"
cb_user_p = os.environ.get('cb_password')
if not cb_user_p:
    print("Error: cb_password environment variable setting is missing!")
    exit(1)
cb_bucket = os.environ.get('cb_bucket')
if not cb_bucket:
    cb_bucket = "greenboard"
is_include_unstable = os.environ.get('is_include_unstable')
if not is_include_unstable:
    print("No result=UNSTABLE jobs included while getting the IPs list")
    is_include_unstable = False
    
#print("Connecting to the greenboard couchbase nosql...")
cluster = Cluster("couchbase://"+cb_host, ClusterOptions(PasswordAuthenticator(cb_user, cb_user_p),
        timeout_options=ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))))
bucket = cluster.bucket(cb_bucket)
doc = bucket.get(cb_build + "_server").value
index = 0
success_count = 0
failure_count = 0
aborted_count = 0
unstable_count = 0
unknown_count = 0
xen_hosts_map = {}
if xen_hosts_file:
    hosts_file = open(xen_hosts_file)
    #print("Please wait while loading the xenhosts information...")
    lines = hosts_file.readlines()
    for line in lines:
        try:
            xen_h = line.split(",")[0]
            xen_vm_ip = line.split(",")[18]
            xen_host_info = line.split(",")[10] +"/" + line.split(",")[9]+"/"+line.split(",")[13]
            xen_hosts_map[xen_vm_ip] = xen_h+"("+xen_host_info+")"
        except:
            pass
    hosts_file.close()
#print("Please wait while getting the aborts and failed tests list...")
print("result,job_name,url,aws_url,servers,hosts(free vcpus/total vcpus/total vms),serverpool_data")
aborted_list = []
failure_list = []
unstable_list = []
for component in doc["os"]["CENTOS"]:
    for job_name in doc["os"]["CENTOS"][component]:
        runs = doc["os"]["CENTOS"][component][job_name]
        fresh_run = runs[-1]
        if fresh_run["result"] == "SUCCESS":
            success_count += 1
        elif fresh_run["result"] == "FAILURE":
            failure_count += 1    
        elif fresh_run["result"] == "ABORTED":
            aborted_count += 1
        elif fresh_run["result"] == "UNSTABLE":
            unstable_count += 1
        else:
            unknown_count += 1    
        if fresh_run["result"] == "FAILURE" or fresh_run["result"] == "ABORTED" or (fresh_run["result"] == "UNSTABLE" and is_include_unstable):
            url = fresh_run["url"] + str(fresh_run["build_id"]) + "/consoleText"
            executor = fresh_run["url"].split('/')[-2] 
            aws_url = "http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/" + cb_build + "/jenkins_logs/" + executor + "/"+ str(fresh_run["build_id"])
            # get xen host details
            req = urllib.request.Request(aws_url+"/jobinfo.json", None)
            req.add_header("Content-Type", "application/json")
            servers = ''
            xen_hosts = ''
            try:
                response = urllib.request.urlopen(req)
                json_data = response.read()
                job_params = json.loads(json_data)
                for param in job_params['actions'][0]['parameters']:
                    if param['name'] == 'servers':
                        servers = param['value'].replace(',',' ').replace('"','')
                        break
                for server in servers.split(' '):
                    xen_hosts += xen_hosts_map[server] + " "
                                
            except:
                pass
            if fresh_run["result"] == "FAILURE":
                failure_list.append("{},{},{},{},{},{},{}".format(fresh_run["result"], job_name, url, aws_url, servers, xen_hosts, get_pool_data(servers)))
            elif fresh_run["result"] == "ABORTED":
                aborted_list.append("{},{},{},{},{},{},{}".format(fresh_run["result"], job_name, url, aws_url, servers, xen_hosts, get_pool_data(servers)))    
            else:
                unstable_list.append("{},{},{},{},{},{},{}".format(fresh_run["result"], job_name, url, aws_url, servers, xen_hosts, get_pool_data(servers))) 
            index += 1

for aborted in aborted_list:
    print(aborted)
for failure in failure_list:
    print(failure)
for unstable in unstable_list:
    print(unstable)
print("{},{},{},{},{},{}".format(aborted_count, failure_count, unstable_count, unknown_count,success_count,
    (aborted_count+failure_count+unknown_count+success_count)))
