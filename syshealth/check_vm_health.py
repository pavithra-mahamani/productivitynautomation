"""
    Generic/Jenkins slave VMs health check
   
    Usage example: 
        python3 check_vm_health.py
        python3 check_vm_health.py <filename-with-ips-in-each-line>
        [ Environment variables needed: vm_windows_password=, vm_linux_password=]

    Output: vm_health_info.csv
"""
import sys
import os
import json
import urllib.request
from datetime import timedelta
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster, ClusterOptions, ClusterTimeoutOptions
from paramiko import SSHClient, AutoAddPolicy
import time

def get_vm_data(servers_list_file):
    vms_list = []
    infile = open(servers_list_file, "r")
    vms_list = infile.readlines()
    data = ''
    try:
        count = 0
        ssh_failed = 0
        ssh_ok = 0
        index = 0
        csvout = open("vm_health_info.csv", "w")
        print("ipaddr,ssh_status,ssh_error,ssh_resp_time(secs),os,cpus,memory_total(kB),memory_free(kB),memory_available(kB),memory_use(%)," + \
                "disk_size(MB),disk_used(MB),disk_avail(MB),disk_use%,uptime,system_time,users,cpu_load_avg_1min,cpu_load_avg_5mins,cpu_load_avg_15mins," + \
                "total_processes")
        csvout.write("ipaddr,ssh_status,ssh_error,ssh_resp_time(secs),os,cpus,memory_total(kB),memory_free(kB),memory_available(kB),memory_use(%)," + \
                "disk_size(MB),disk_used(MB),disk_avail(MB),disk_use%,uptime,system_time,users,cpu_load_avg_1min,cpu_load_avg_5mins,cpu_load_avg_15mins," \
                "total_processes")
        for ip in vms_list:
            index += 1
            ipaddr = ip.rstrip()
            os_name = os.environ.get('os','linux')
            try:
                ssh_status, ssh_error, ssh_resp_time, os_version, cpus, meminfo, diskinfo, uptime, systime, cpu_load, cpu_proc = check_vm(os_name,ipaddr.rstrip())
                if ssh_status == 'ssh_failed':
                    ssh_state=0
                    ssh_failed += 1
                else:
                    ssh_state=1
                    ssh_ok += 1
                print("{},{},{},{},{},{},{},{},{},{},{},{},{}".format(index, ipaddr, ssh_status, ssh_error, ssh_resp_time, os_version, cpus, meminfo, diskinfo, uptime, systime, cpu_load, cpu_proc))
                csvout.write("\n{},{},{},{},{},{},{},{},{},{},{},{}".format(ipaddr, ssh_state, ssh_error, ssh_resp_time, os_version, cpus, meminfo, diskinfo, uptime, systime, cpu_load, cpu_proc))
                csvout.flush()
            except Exception as ex:
                print(ex)
                pass
            count +=1
        
        print("ssh_ok={},ssh_failed={},total={}".format(ssh_ok, ssh_failed,count))
        csvout.close()
    except Exception as fex :
        print(fex)
        #print("exception:", sys.exc_info()[0])

def check_vm(os_name, host):
    config = os.environ
    ssh_resp_time = ''
    start = 0
    end = 0
    if '[' in host:
        host = host.replace('[','').replace(']','')
    if "windows" in os_name:
        username = 'Administrator' if not config.get("vm_windows_username") else config.get("vm_windows_username")
        password = config.get("vm_windows_password")
    else:
        username = 'root' if not config.get("vm_linux_username") else config.get("vm_linux_username")
        password = config.get("vm_linux_password")
    try:
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        ssh_connect_timeout = int(config.get("ssh_connect_timeout", 45))
        start = time.time()
        client.connect(
            host,
            username=username,
            password=password,
            timeout=ssh_connect_timeout,
            look_for_keys=False
        )
        end = time.time()
        ssh_resp_time = "{:4.2f}".format(end-start)
        cpus = get_cpuinfo(client)
        meminfo = get_meminfo(client)
        diskinfo = get_diskinfo(client)
        uptime = get_uptime(client)
        systime = get_system_time(client)
        cpu_load = get_cpu_users_load_avg(client)
        cpu_total_processes = get_total_processes(client)
        os_version = get_os_version(client)

        while len(meminfo.split(','))<3:
            meminfo += ','
        mem_total = meminfo.split(',')[0]
        mem_avail = meminfo.split(',')[2]
        if mem_avail and mem_total:
            meminfo += ","+ str(round(((int(mem_total)-int(mem_avail))/int(mem_total))*100))
        while len(cpu_load.split(','))<4:
            cpu_load += ','
        client.close()
    except Exception as e:
        meminfo = ',,,'
        diskinfo = ',,,'
        cpu_load = ',,,'
        if end == 0:
            end = time.time()
            ssh_resp_time = "{:4.2f}".format(end-start)
        return 'ssh_failed', ssh_resp_time, str(e).replace(',',' '), '', '', meminfo, diskinfo,'','',cpu_load, ''
    return 'ssh_ok', '', ssh_resp_time, os_version, cpus, meminfo, diskinfo, uptime, systime, cpu_load, cpu_total_processes

def get_cpuinfo(ssh_client):
    return ssh_command(ssh_client,"cat /proc/cpuinfo  |egrep processor |wc -l")

def get_meminfo(ssh_client):
    return ssh_command(ssh_client,"cat /proc/meminfo |egrep Mem |cut -f2- -d':'|sed 's/ //g'|xargs|sed 's/ /,/g'|sed 's/kB//g'")

def get_diskinfo(ssh_client):
    return ssh_command(ssh_client,"df -ml --output=size,used,avail,pcent / |tail -1 |sed 's/ \+/,/g'|cut -f2- -d','|sed 's/%//g'")

def get_system_time(ssh_client):
    return ssh_command(ssh_client, "TZ='America/Los_Angeles' date '+%Y-%m-%d %H:%M:%S'")

def get_uptime(ssh_client):
    return ssh_command(ssh_client, "uptime -s")

def get_cpu_users_load_avg(ssh_client):
    return ssh_command(ssh_client, "uptime |rev|cut -f1-4 -d','|rev|sed 's/load average://g'|sed 's/ \+//g'|sed 's/users,/,/g'|sed 's/user,/,/g'")

def get_total_processes(ssh_client):
    return ssh_command(ssh_client, "ps aux | egrep -v COMMAND | wc -l")

def get_os_version(ssh_client):
    return ssh_command(ssh_client, "cat /etc/*release* |egrep PRETTY|cut -f2 -d'='|xargs")

def ssh_command(ssh_client, cmd):
    ssh_output = ''
    ssh_error = ''
    try:
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_client.exec_command(cmd)
        
        for line in iter(ssh_stdout.readline, ""):
            ssh_output += line
        if ssh_output:
            ssh_output = str(ssh_output).rstrip()
        for line in iter(ssh_stderr.readline, ""):
            ssh_error += line
    except:
        print("cmd={},error={}".format(cmd,ssh_error))

    return ssh_output

def main():
    if len(sys.argv) < 2:
        print("Usage: {} {}".format(sys.argv[0], "<vms_file> [xen_hosts_file] "))
        print("Environment: vm_linux_username=root, vm_linux_password=")
        exit(1)
    vm_list_file = sys.argv[1]
    xen_hosts_file = ''
    if len(sys.argv) > 2:
        xen_hosts_file = sys.argv[2]
    get_vm_data(vm_list_file)


if __name__ == '__main__':
    main()

