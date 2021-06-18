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
import multiprocessing as mp
import time
import datetime
import uuid


def get_pool_data(pools):
    pools_list = []
    for pool in pools.split(','):
        pools_list.append(pool)
    
    query = "SELECT ipaddr, os, state, origin, poolId, username FROM `QE-server-pool` WHERE poolId in [" \
                + ', '.join('"{0}"'.format(p) for p in pools_list) + "] or " \
                + ' or '.join('"{0}" in poolId'.format(p) for p in pools_list)
    is_debug = os.environ.get('is_debug')
    if is_debug:
        print("Query:{};".format(query))
    pool_cb_host = os.environ.get('pool_cb_host', "172.23.104.162")
    pool_cb_user = os.environ.get('pool_cb_user', "Administrator")
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
        print("ipaddr,ssh_status,ssh_error,ssh_resp_time(secs),pool_os,real_os,os_match_state,pool_state,pool_ids,pool_user,cpus,memory_total(kB),memory_free(kB),memory_available(kB),memory_use(%)," + \
                "disk_size(MB),disk_used(MB),disk_avail(MB),disk_use%,uptime,booted(days),system_time,users,cpu_load_avg_1min,cpu_load_avg_5mins,cpu_load_avg_15mins," + \
                "total_processes,couchbase_process,couchbase_version,couchbase_services,cb_data_kv_status,cb_index_status,cb_query_status,cb_search_status,cb_analytics_status,cb_eventing_status,cb_xdcr_status")
        csv_head = "ipaddr,ssh_status,ssh_error,ssh_resp_time(secs),pool_os,real_os,os_match_state,pool_state,pool_ids,pool_user,cpus,memory_total(kB),memory_free(kB),memory_available(kB),memory_use(%)," + \
                "disk_size(MB),disk_used(MB),disk_avail(MB),disk_use%,uptime,booted(days),system_time,users,cpu_load_avg_1min,cpu_load_avg_5mins,cpu_load_avg_15mins," \
                "total_processes,couchbase_process,couchbase_version,couchbase_services,cb_data_kv_status,cb_index_status,cb_query_status,cb_search_status,cb_analytics_status,cb_eventing_status,cb_xdcr_status"
        csvout.write(csv_head)
        os_mappings={"centos":"centos linux 7 (core)", "centosnonroot":"centos linux 7 (core)", "debian10":"debian gnu/linux 10 (buster)", \
                    "oel8":"oracle linux server 8.1", "rhel":"red hat enterprise linux", "rhel8":"red hat enterprise linux 8.3 (ootpa)", \
                    "suse12":"suse linux enterprise server 12 sp2", "opensuse15":"opensuse leap 15.1","suse15":"suse linux enterprise server 15", \
                    "opensuse15hostname":"opensuse leap 15.1","suse15hostname":"suse linux enterprise server 15","ubuntu18":"ubuntu 18", \
                    "ubuntu20":"ubuntu 20", "windows2019":"windows" }
        for row in result:
            index += 1
            try:
                ssh_status, ssh_error, ssh_resp_time, real_os, cpus, meminfo, diskinfo, uptime, uptime_days, systime, cpu_load, cpu_proc, cb_proc, cb_version, cb_serv, cb_ind_serv = check_vm(row['os'],row['ipaddr'])
                if ssh_status == 'ssh_failed':
                    ssh_state=0
                    ssh_failed += 1
                else:
                    ssh_state=1
                    ssh_ok += 1
                os_state = 0
                if real_os:
                    pool_os = row['os'].lower()
                    if pool_os in os_mappings.keys() and os_mappings[pool_os] in real_os.lower():
                        os_state = 1
                    elif pool_os in os_mappings.keys() and pool_os.startswith('suse15'):
                        if os_mappings['open'+pool_os] == real_os.lower():
                            os_state = 1
                    
                print("{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(index, row['ipaddr'], ssh_status, ssh_error, ssh_resp_time, row['os'], real_os, \
                    os_state, row['state'],  '+'.join("{}".format(p) for p in row['poolId']), row['username'], cpus, meminfo, diskinfo, uptime, uptime_days, systime, cpu_load, cpu_proc, cb_proc, cb_version, cb_serv, cb_ind_serv))
                csv_row = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(row['ipaddr'], ssh_state, ssh_error, ssh_resp_time, row['os'], real_os, \
                    os_state, row['state'],  '+'.join("{}".format(p) for p in row['poolId']), row['username'], cpus, meminfo, diskinfo, uptime, uptime_days, systime, cpu_load, cpu_proc, cb_proc, cb_version, cb_serv, cb_ind_serv)
                csvout.write("\n{}".format(csv_row))
                csvout.flush()
                ipaddr = row['ipaddr']
                is_save_cb = bool(os.environ.get("is_save_cb"))
                if is_save_cb:
                    cb_doc = CBDoc()
                    doc_val = {}
                    keys = csv_head.split(",")
                    values = csv_row.split(",")
                    for index in range(0, len(keys)):
                        doc_val[keys[index]] = values[index]
                    doc_val['type'] = 'static_server_pool_vm'
                    doc_val['created_time'] = time.time()
                    doc_val['created_timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    doc_key = "{}_{}".format(ipaddr, str(uuid.uuid4())) 
                    cb_doc.save_doc(doc_key, doc_val)
            except Exception as ex:
                print(ex)
                pass
            count +=1
        booked_count = get_pool_state_count(pool_cluster, pools_list, 'booked')
        avail_count = get_pool_state_count(pool_cluster, pools_list, 'available')
        using_count = booked_count + avail_count
        print("ssh_ok={},ssh_failed={},total={},booked={},avail={},using={}".format(ssh_ok, ssh_failed,count, booked_count, avail_count, using_count))
        csvout.close()
    except Exception as fex :
        print(fex)
        #print("exception:", sys.exc_info()[0])


def get_pool_data_parallel(pools):
    pools_list = []
    for pool in pools.split(','):
        pools_list.append(pool)
    
    query = "SELECT ipaddr, os, state, origin, poolId, username FROM `QE-server-pool` WHERE poolId in [" \
                + ', '.join('"{0}"'.format(p) for p in pools_list) + "] or " \
                + ' or '.join('"{0}" in poolId'.format(p) for p in pools_list)
    is_debug = os.environ.get('is_debug')
    if is_debug:
        print("Query:{};".format(query))
    pool_cb_host = os.environ.get('pool_cb_host', "172.23.104.162")
    pool_cb_user = os.environ.get('pool_cb_user', "Administrator")
    pool_cb_user_p = os.environ.get('pool_cb_password')
    if not pool_cb_user_p:
        print("Error: pool_cb_password environment variable setting is missing!")
        exit(1)
    try:
        retry_count = int(os.environ.get('retry_count', 3))
        query_done = False
        while not query_done and retry_count != 0:
            try:
                pool_cluster = Cluster("couchbase://"+pool_cb_host, ClusterOptions(PasswordAuthenticator(pool_cb_user, pool_cb_user_p),
                timeout_options=ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))))
                result = pool_cluster.query(query)
                query_done = True
            except:
                print("Got an error: {} and retrying after 5 secs...at {}, query_done={}, retry_count down {}".format(sys.exc_info()[0], pool_cb_host, query_done, retry_count))
                time.sleep(5)
                retry_count -= 1

        csvout = open("pool_vm_health_info.csv", "w")
        print("ipaddr,ssh_status,ssh_error,ssh_resp_time(secs),pool_os,real_os,os_match_state,pool_state,pool_ids,pool_user,cpus,memory_total(kB),memory_free(kB),memory_available(kB),memory_use(%)," + \
                "disk_size(MB),disk_used(MB),disk_avail(MB),disk_use%,uptime,booted(days),system_time,users,cpu_load_avg_1min,cpu_load_avg_5mins,cpu_load_avg_15mins," + \
                "total_processes,couchbase_process,couchbase_version,couchbase_services,cb_data_kv_status,cb_index_status,cb_query_status,cb_search_status,cb_analytics_status,cb_eventing_status,cb_xdcr_status")
        csv_head = "ipaddr,ssh_status,ssh_error,ssh_resp_time(secs),pool_os,real_os,os_match_state,pool_state,pool_ids,pool_user,cpus,memory_total(kB),memory_free(kB),memory_available(kB),memory_use(%)," + \
                "disk_size(MB),disk_used(MB),disk_avail(MB),disk_use%,uptime,booted(days),system_time,users,cpu_load_avg_1min,cpu_load_avg_5mins,cpu_load_avg_15mins," \
                "total_processes,couchbase_process,couchbase_version,couchbase_services,cb_data_kv_status,cb_index_status,cb_query_status,cb_search_status,cb_analytics_status,cb_eventing_status,cb_xdcr_status"
        csvout.write(csv_head)
        
        mp_pool = mp.Pool(mp.cpu_count())
        data = mp_pool.map(get_pool_data_vm_parallel, [row for row in result])
        mp_pool.close()

        count = 0
        ssh_failed = 0
        ssh_ok = 0
        for r in data:
            count += 1
            ssh_status=r.split(',')[1]
            if int(ssh_status) == 1:
                ssh_ok += 1
            else:
                ssh_failed += 1
            print("{},{}".format(count,r))
            csvout.write("\n{}".format(r))
            csvout.flush()
            csv_row = r
            is_save_cb = bool(os.environ.get("is_save_cb"))
            if is_save_cb:
                cb_doc = CBDoc()
                doc_val = {}
                keys = csv_head.split(",")
                values = csv_row.split(",")
                ipaddr = values[0]
                for index in range(0, len(keys)):
                    doc_val[keys[index]] = values[index]
                doc_val['type'] = 'static_server_pool_vm'
                doc_val['created_time'] = time.time()
                doc_val['created_timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                doc_key = "{}_{}".format(ipaddr, str(uuid.uuid4())) 
                cb_doc.save_doc(doc_key, doc_val)
            
        booked_count = get_pool_state_count(pool_cluster, pools_list, 'booked')
        avail_count = get_pool_state_count(pool_cluster, pools_list, 'available')
        using_count = booked_count + avail_count
        print("ssh_ok={},ssh_failed={},total={},booked={},avail={},using={}".format(ssh_ok, ssh_failed,count, booked_count, avail_count, using_count))
        csvout.close()
    except Exception as fex :
        print(fex)
        #print("exception:", sys.exc_info()[0])

def get_pool_data_vm_parallel(row):    
    try:
        os_mappings={"centos":"centos linux 7 (core)", "centosnonroot":"centos linux 7 (core)", "debian10":"debian gnu/linux 10 (buster)", \
                    "oel8":"oracle linux server 8.1", "rhel":"red hat enterprise linux", "rhel8":"red hat enterprise linux 8.3 (ootpa)", \
                    "suse12":"suse linux enterprise server 12 sp2", "opensuse15":"opensuse leap 15.1","suse15":"suse linux enterprise server 15", \
                    "opensuse15hostname":"opensuse leap 15.1","suse15hostname":"suse linux enterprise server 15","ubuntu18":"ubuntu 18", \
                    "ubuntu20":"ubuntu 20", "windows2019":"windows" }

        ssh_status, ssh_error, ssh_resp_time, real_os, cpus, meminfo, diskinfo, uptime, uptime_days, systime, cpu_load, cpu_proc, cb_proc, cb_version, cb_serv, cb_ind_serv = check_vm(row['os'],row['ipaddr'])
        if ssh_status == 'ssh_failed':
            ssh_state=0
        else:
            ssh_state=1
        
        os_state = 0
        if real_os:
            pool_os = row['os'].lower()
            if pool_os in os_mappings.keys() and os_mappings[pool_os] in real_os.lower():
                os_state = 1
            elif pool_os in os_mappings.keys() and pool_os.startswith('suse15'):
                if os_mappings['open'+pool_os] == real_os.lower():
                    os_state = 1
            
        return "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(row['ipaddr'], ssh_state, ssh_error, ssh_resp_time, row['os'], real_os, \
            os_state, row['state'],  '+'.join("{}".format(p) for p in row['poolId']), row['username'], cpus, meminfo, diskinfo, uptime, uptime_days, systime, cpu_load, cpu_proc, cb_proc, cb_version, cb_serv, cb_ind_serv)
        
    except Exception as ex:
        print(ex)
        pass

def get_pool_state_count(pool_cluster, pools_list, pool_state):
    query = "SELECT count(*) as count FROM `QE-server-pool` WHERE state='" + pool_state + "' and (poolId in [" \
                + ', '.join('"{0}"'.format(p) for p in pools_list) + "] or " \
                + ' or '.join('"{0}" in poolId'.format(p) for p in pools_list) \
                + ')'
    is_debug = os.environ.get('is_debug')
    if is_debug:
        print("Query:{};".format(query))
    count = 0
    result = pool_cluster.query(query)
    for row in result:
        count = row['count']
    return count

def check_vm(os_name, host):
    config = os.environ
    ssh_resp_time = ''
    start = 0
    end = 0
    if '[' in host:
        host = host.replace('[','').replace(']','')
    if "win" in os_name:
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
        uptime_days = ''
        if uptime:
            utime = time.strptime(uptime, '%Y-%m-%d %H:%M:%S')
            uptime_days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(time.mktime(utime))).days
        systime = get_system_time(client)
        cpu_load = get_cpu_users_load_avg(client)
        cpu_total_processes = get_total_processes(client)
        if 'win' in os_name:
            real_os_version = get_os_win_version(client)
        else:
            real_os_version = get_os_version(client)
        cb_processes = get_cb_processes(client)
        cb_running_serv = get_cb_running_services(client)
        cb_version = get_cb_version(client)

        while len(meminfo.split(','))<3:
            meminfo += ','
        mem_total = meminfo.split(',')[0]
        mem_free = meminfo.split(',')[1]
        mem_avail = meminfo.split(',')[2]
        if mem_avail and mem_total:
            meminfo += ","+ str(round(((int(mem_total)-int(mem_avail))/int(mem_total))*100))
        elif mem_free and mem_total:
            meminfo += ","+ str(round(((int(mem_total)-int(mem_free))/int(mem_total))*100))
        else:
            meminfo += ','
        
        while len(diskinfo.split(','))<4:
            diskinfo += ','

        while len(cpu_load.split(','))<4:
            cpu_load += ','
        cb_serv_data = 0
        cb_serv_index = 0
        cb_serv_query = 0
        cb_serv_search = 0
        cb_serv_analytics = 0
        cb_serv_eventing = 0
        cb_serv_xdcr = 0
        if 'data' in cb_running_serv:
            cb_serv_data = 1
        if 'index' in cb_running_serv:
            cb_serv_index = 1
        if 'query' in cb_running_serv:
            cb_serv_query = 1
        if 'search' in cb_running_serv:
            cb_serv_search = 1
        if 'analytics' in cb_running_serv:
            cb_serv_analytics = 1
        if 'eventing' in cb_running_serv:
            cb_serv_eventing = 1
        if 'xdcr' in cb_running_serv:
            cb_serv_xdcr = 1
        cb_ind_serv = "{},{},{},{},{},{},{}".format(cb_serv_data, cb_serv_index, cb_serv_query, cb_serv_search, cb_serv_analytics, cb_serv_eventing, cb_serv_xdcr)
    
        client.close()
    except Exception as e:
        meminfo = ',,,'
        diskinfo = ',,,'
        cpu_load = ',,,'
        cb_ind_serv = ',,,,,,'
        if end == 0:
            end = time.time()
            ssh_resp_time = "{:4.2f}".format(end-start)
        return 'ssh_failed', str(e).replace(',',' '), ssh_resp_time, '', '', '', meminfo, diskinfo,'','',cpu_load, '', '', '','', cb_ind_serv
    return 'ssh_ok', '', ssh_resp_time, real_os_version, cpus, meminfo, diskinfo, uptime, uptime_days, systime, cpu_load, cpu_total_processes, cb_processes, cb_version, cb_running_serv, cb_ind_serv

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

def get_os_win_version(ssh_client):
    return ssh_command(ssh_client, "cat /etc/hosts |egrep Windows |rev|cut -f1 -d' '|rev|cut -f1 -d'.'")

def get_cb_processes(ssh_client):
    return ssh_command(ssh_client, "ps -o comm `pgrep -f couchbase` |egrep -v COMMAND |wc -l")

def get_cb_running_services(ssh_client):
    cb_processes = ssh_command(ssh_client, "ps -o comm `pgrep -f couchbase`|egrep -v COMMAND | xargs")
    cb_services = []
    for proc in cb_processes.split(' '):
        if proc == 'memcached':
            cb_services.append('data(kv)')
        elif proc == 'indexer':
            cb_services.append('index')
        elif proc == 'cbq-engine':
            cb_services.append('query(n1ql)')
        elif proc == 'cbft':
            cb_services.append('search(fts)')
        elif proc == 'cbas':
            cb_services.append('analytics(cbas)')
        elif proc == 'eventing-produc':
            cb_services.append('eventing')
        elif proc == 'goxdcr':
            cb_services.append('xdcr')
    cb_services.sort()
    return ' '.join(cb_services)
        
def get_cb_version(ssh_client):
    return ssh_command(ssh_client, "if [ -f /opt/couchbase/VERSION.txt ]; then cat /opt/couchbase/VERSION.txt; fi")

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

class CBDoc:
    def __init__(self):
        config = os.environ
        self.cb_host = config.get("health_cb_host", "172.23.104.180")
        self.cb_bucket = config.get("health_cb_bucket", "QE-staticserver-pool-health")
        self.cb_username = config.get("health_cb_username", "Administrator")
        self.cb_userpassword = config.get("health_cb_password")
        if not self.cb_userpassword:
            print("Setting of env variable: heal_cb_password= is needed!")
            return
        try:
            self.cb_cluster = Cluster("couchbase://"+self.cb_host, ClusterOptions(PasswordAuthenticator(self.cb_username, self.cb_userpassword), \
                                    timeout_options=ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))))
            self.cb_b = self.cb_cluster.bucket(self.cb_bucket)
            self.cb = self.cb_b.default_collection()
            
        except Exception as e:
            print('Connection Failed: %s ' % self.cb_host)
            print(e)

    def get_doc(self, doc_key, retries=3):
        while retries > 0:
            try:
                return self.cb.get(doc_key)
            except Exception as e:
                print('Error while getting doc %s !' % doc_key)
                print(e)
            time.sleep(5)
            retries -= 1

    def save_doc(self, doc_key, doc_value, retries=3):
        while retries > 0:
            try:
                self.cb.upsert(doc_key, doc_value)
                print("%s added/updated successfully" % doc_key)
                break
            except Exception as e:
                print('Document with key: %s saving error' % doc_key)
                print(e)
            time.sleep(5)
            retries -= 1

    def remove_doc(self, ip, retries=3):
        while retries > 0:
            try:
                static_doc_value = self.static_cb.get(ip).value
                self.static_cb.remove(ip)
                log.info("{} removed from static pools: {}".format(ip, ",".join(static_doc_value["poolId"])))
                break
            except NotFoundError:
                break
            except Exception as e:
                print("Error removing {} from static pools".format(ip))
                print(e)
            time.sleep(5)
            retries -= 1
    
def main():
    if len(sys.argv) < 2:
        print("Usage: {} {}".format(sys.argv[0], "<pool> [xen_hosts_file] "))
        print("Environment: pool_cb_password=, [pool_cb_host=172.23.104.162, pool_cb_user=Administrator]")
        exit(1)
    pools = sys.argv[1]
    xen_hosts_file = ''
    if len(sys.argv) > 2:
        xen_hosts_file = sys.argv[2]
    
    is_seq_run = os.environ.get('is_seq_run')
    if is_seq_run:
        get_pool_data(pools)
    else:
        get_pool_data_parallel(pools)

if __name__ == '__main__':
    main()

