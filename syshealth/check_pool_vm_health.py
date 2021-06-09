"""
    QE static pool VMs health check
   
    Usage example: 
        python3 check_pool_vm_health.py
        python3 check_pool_vm_health.py regression,12hrreg,security
        [ Environment variables needed: pool_cb_password=, vm_windows_password=, vm_linux_password=]

    Output: pool_vm_health_info.csv
"""
import sys
import os
import json
import urllib.request
from datetime import timedelta
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster, ClusterOptions, ClusterTimeoutOptions
from paramiko import SSHClient, AutoAddPolicy

def get_pool_data(pools):
    pools_list = []
    for pool in pools.split(','):
        pools_list.append(pool)
    
    query = "SELECT ipaddr, os, state, origin, poolId FROM `QE-server-pool` WHERE poolId in [" \
                + ', '.join('"{0}"'.format(p) for p in pools_list) + "] or " \
                + ' or '.join('"{0}" in poolId'.format(p) for p in pools_list)
    pool_cb_host = os.environ.get('pool_cb_host')
    if not pool_cb_host:
        pool_cb_host = "172.23.104.162"
    pool_cb_user = os.environ.get('pool_cb_user')
    if not pool_cb_user:
        pool_cb_user = "Administrator"
    pool_cb_user_p = os.environ.get('pool_cb_password')
    if not pool_cb_user_p:
        print("Error: pool_cb_password environment variable setting is missing!")
        exit(1)
    data = ''
    try:
        pool_cluster = Cluster("couchbase://"+pool_cb_host, ClusterOptions(PasswordAuthenticator(pool_cb_user, pool_cb_user_p),
        timeout_options=ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))))
        result = pool_cluster.query(query)
        count = 0
        ssh_failed = 0
        ssh_ok = 0
        index = 0
        csvout = open("pool_vm_health_info.csv", "w")
        print("ipaddr,ssh_status,ssh_error,os,pool_state,pool_ids")
        csvout.write("ipaddr,ssh_status,ssh_error,os,pool_state,pool_ids")
        for row in result:
            index += 1
            try:
                ssh_status, ssh_error = check_vm(row['os'],row['ipaddr'])
                if ssh_status == 'ssh_failed':
                    ssh_failed += 1
                else:
                    ssh_ok += 1
                print("{},{},{},{},{},{},{}".format(index, row['ipaddr'], ssh_status, ssh_error, row['os'], \
                    row['state'],  '+'.join("{}".format(p) for p in row['poolId'])))
                csvout.write("\n{},{},{},{},{},{}".format(row['ipaddr'], ssh_status, ssh_error, row['os'], \
                    row['state'],  '+'.join("{}".format(p) for p in row['poolId'])))
                csvout.flush()
            except:
                pass
            count +=1
        print("ssh_ok={},ssh_failed={},total={}".format(ssh_ok, ssh_failed,count))
        csvout.close()
    except:
        print("exception:", sys.exc_info()[0])
    
def check_vm(os_name, host):
    config = os.environ
    if '[' in host:
        host = host.replace('[','').replace(']','')
    if os_name == "windows":
        username = 'Administrator' if not config.get("vm_windows_username") else config.get("vm_windows_username")
        password = config.get("vm.windows.password")
    else:
        username = 'root' if not config.get("vm_linux_username") else config.get("vm_linux_username")
        password = config.get("vm_linux_password")
    try:
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(
            host,
            username=username,
            password=password,
            timeout=30
        )
        client.close()
    except Exception as e:
        print(e)
        return 'ssh_failed', str(e).replace(',',' ')
    return 'ssh_ok', ''

def main():
    if len(sys.argv) < 2:
        print("Usage: {} {}".format(sys.argv[0], "<pool> [xen_hosts_file] "))
        print("Environment: pool_cb_password=, [pool_cb_host=172.23.104.162, pool_cb_user=Administrator]")
        exit(1)
    pools = sys.argv[1]
    xen_hosts_file = ''
    if len(sys.argv) > 2:
        xen_hosts_file = sys.argv[2]
    get_pool_data(pools)


if __name__ == '__main__':
    main()

