"""
    QE Infrastructure - Xen Hosts and Xen VMs 
    Purpose: Extraction of summary details in .csv file

    Usage: python3 xenhosts_summary.py 
"""
import sys
import os
import argparse
import json
import re
import paramiko
import XenAPI

index=1

def main(session,host, csvout, username, password):
    get_host_summary(session, host, csvout, username, password)

def get_host_summary(session, host, csvout, username, password):
    global grandvms
    host_physical_cpu_count = get_physical_cpuinfo(host, username, password)
    host_dom0_vcpus = get_control_domain_vcpus(host, username, password)
    host_records = session.xenapi.host.get_all_records()
    #print(host_records)
    for host_info in host_records:
        host_label = host_records[host_info]['name_label'].replace(',',' ')
        host_ip = host_records[host_info]['address']
        #host_physical_cpu_count = host_records[host_info]['cpu_info']['cpu_count']
        host_physical_cpu_socket_count = host_records[host_info]['cpu_info']['socket_count']
        host_product_manufacturer = host_records[host_info]['bios_strings']['system-manufacturer']
        host_product_name = host_records[host_info]['bios_strings']['system-product-name']
        host_xen_version = host_records[host_info]['software_version']['xen']
    
    patches = session.xenapi.pool_patch.get_all()
    patch_count = len(patches)
    vm_count, xen_cpu_count_free, xen_memory_free_gb, xen_cpu_count_total, xen_memory_total_gb = \
        get_host_usage(session)
    xen_cpu_count_free -= int(host_dom0_vcpus)
    #print("{},{},{},{} {},{},{},{},{},{},{},{},{}".format(host, host_ip, host_label, host_product_manufacturer, host_product_name, host_xen_version, 
    #    patch_count, host_physical_cpu_count, 
    #    host_physical_cpu_socket_count, 
    #    xen_cpu_count_total, xen_cpu_count_free, 
    #    xen_memory_total_gb, xen_memory_free_gb))       
    vms = session.xenapi.VM.get_all()
    #vm_count = 0
    #vm_summary = ''
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        if not (record["is_a_template"]) and not (record["is_control_domain"]) and (record["power_state"]!='Halted'):
            name = record["name_label"]
            power_state = record["power_state"]
            vcpus = record["VCPUs_max"]
            memory_static_max = int(int(record["memory_static_max"]) / (1024 * 1024 * 1024))
            #hostaddress = record['host.address']
            metricsRef = record['guest_metrics']
            metrics = session.xenapi.VM_guest_metrics.get_record(metricsRef)
            #print(metrics)
            try:
                os_version_name = metrics['os_version']['name']
                os_version_distro = metrics['os_version']['distro']
                os_version_uname = metrics['os_version']['uname']
            except:
                os_version_name = ''
                os_version_distro = ''
                os_version_uname = ''

            ipAddr0 =''
            if '0/ip' in metrics['networks']:
                ipAddr0 = metrics['networks']['0/ip']
            else:
                pattern = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
                try:
                    ipAddr0 = pattern.search(name)[0]
                except:
                    pass
            #networkinfo = ','.join([str(elem) for elem in metrics['networks'].values()])
            

            vm_data = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(host, host_ip, host_label, host_product_manufacturer, 
                    host_product_name, host_xen_version, patch_count, host_physical_cpu_count, 
                    host_physical_cpu_socket_count, xen_cpu_count_total, xen_cpu_count_free, 
                    xen_memory_total_gb, xen_memory_free_gb, vm_count, name, power_state, vcpus, memory_static_max, ipAddr0, 
                    os_version_distro, os_version_name, os_version_uname)
            print("{}".format(vm_data))
            csvout.write("\n{}".format(vm_data))
            #if vm_summary:
            #    vm_summary += "\n" + vm_data
            #else:
            #    vm_summary += ",{},{},{},{},{},{},{},{}".format(name,  power_state, vcpus, memory_static_max, ipAddr0, 
            #        os_version_distro, os_version_name, os_version_uname)
            #vm_count += 1

    #csvout.write("\n{},{},{},{} {},{},{},{},{},{},{},{},{},{}{}".format(host, host_ip, host_label, host_product_manufacturer, 
    #    host_product_name, host_xen_version, 
    #    patch_count, host_physical_cpu_count, 
    #    host_physical_cpu_socket_count, 
    #    xen_cpu_count_total, xen_cpu_count_free, 
    #    xen_memory_total_gb, xen_memory_free_gb, vm_count, vm_summary))
    csvout.flush()
    print("={}\n".format(vm_count))
    grandvms += vm_count

def get_physical_cpuinfo(host, username, password):
    pcpus = ssh_command(host, username, password,"cat /proc/cpuinfo  |egrep processor |wc -l")
    if pcpus:
        pcpus = pcpus.rstrip()
    return pcpus
     

def ssh_command(host, username, password, cmd):
    ssh_output = ''
    ssh_error = ''
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password, timeout=5)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
        
        for line in iter(ssh_stdout.readline, ""):
            ssh_output += line
        for line in iter(ssh_stderr.readline, ""):
            ssh_error += line    
        ssh.close()
    except:
        print("cmd={},error={}".format(cmd,ssh_error))

    return ssh_output

def get_host_usage(session):
    vm_count, vm_cpus, vm_memory = get_vms_usage(session)
    host_ref = session.xenapi.session.get_this_host(session.handle)
    xen_host_record = session.xenapi.host.get_record(host_ref)
    xen_cpu_count_total = int(xen_host_record['cpu_info']['cpu_count'])
    xen_cpu_count_free = xen_cpu_count_total - vm_cpus
    xen_host_metrics_ref = session.xenapi.host.get_metrics(host_ref)
    metrics = session.xenapi.host_metrics.get_record(xen_host_metrics_ref)
    xen_memory_free_gb = int(int(metrics['memory_free']) / (1024 * 1024 * 1024))
    xen_memory_total_gb = int(int(metrics['memory_total']) / (1024 * 1024 * 1024))
    return vm_count, xen_cpu_count_free, xen_memory_free_gb, xen_cpu_count_total, xen_memory_total_gb

def get_control_domain_vcpus(host, username, password):
    pcpus = ssh_command(host, username, password,"xentop -bi1|egrep Dom|xargs|cut -f9 -d' '")
    if pcpus:
        pcpus = pcpus.rstrip()
    return pcpus

def get_vms_usage(session):
    vms = session.xenapi.VM.get_all()
    count = 0
    vcpus = 0
    memory_static_max = 0
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        if not (record["is_a_template"]) and not (record["is_control_domain"]) and (
                record["power_state"] != 'Halted'):    
            count = count + 1
            vcpus = vcpus + int(record["VCPUs_max"])
            memory_static_max = memory_static_max + int(
                int(record["memory_static_max"]) / (1024 * 1024 * 1024))
    print("count={},vcpus={},memory={}".format(count, vcpus, memory_static_max))
    return count, vcpus, memory_static_max

def get_patches_info(session, host):
    patches = session.xenapi.pool_update.get_all()
    print ("Server has %d patches:" % (len(patches)))
    for patch in patches:
        print("{}, patch={}".format(host, patch))

def get_vms_info(session, host):
    global index, grandvms
    vms = session.xenapi.VM.get_all()
    #print ("Server has %d VM objects (this includes templates):" % (len(vms)))

    
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        #print("vm record:",record)
        if not (record["is_a_template"]) and not (record["is_control_domain"]) and (record["power_state"]!='Halted'):
            name = record["name_label"]
            name_description = record["name_description"]
            uuid = record["uuid"]
            power_state = record["power_state"]
            vcpus = record["VCPUs_max"]
            memory_static_max = record["memory_static_max"]
            hostVIFs = record['VIFs']
            #hostaddress = record['host.address']
            ipRef = session.xenapi.VM_guest_metrics.get_record(record['guest_metrics'])
            #print(ipRef)
            #ipAdd0 = ipRef['networks']['0/ip']
            networkinfo = ','.join([str(elem) for elem in ipRef['networks'].values()]) 
            #print("VM#"+str(index)+","+name+","+ipAdd0+","+power_state+","+vcpus+","+memory_static_max+","+name_description)
            print(str(index)+","+host+","+name+","+power_state+","+vcpus+","+memory_static_max+","+networkinfo)
            #print("ipAdd0="+ipAdd0)

            index=index+1
            #grandvms+=index


if __name__ == "__main__":

    defaulthosts = ["xcp-s418.sc.couchbase.com","xcp-s823.sc.couchbase.com","xcp-s823.sc.couchbase.com","xcp-s719.sc.couchbase.com",
             "xcp-s440.sc.couchbase.com","xcp-s121.sc.couchbase.com","xcp-s021.sc.couchbase.com","xcp-s022.sc.couchbase.com",
             "xcp-s411.sc.couchbase.com","172.23.110.17","xcp-sa28.sc.couchbase.com",
             "xcp-s123.sc.couchbase.com","xcp-s436.sc.couchbase.com","xcp-s606.sc.couchbase.com"]
    qeserverhosts = ["172.23.110.20","xcp-s225.sc.couchbase.com","xcp-s719.sc.couchbase.com","172.23.99.214","172.23.98.84",
    "172.23.108.18","172.23.105.150","172.23.105.207","xcp-s440.sc.couchbase.com","xcp-s418.sc.couchbase.com","172.23.120.5",
    "172.23.104.62","xcp-s620.sc.couchbase.com","172.23.109.148","172.23.98.194","xcp-s840.sc.couchbase.com","172.23.97.233",
    "172.23.120.4","172.23.104.112","172.23.104.48","xcp-s706.sc.couchbase.com","xcp-s313.sc.couchbase.com","172.23.106.7",
    "172.23.109.167","xcp-s205.sc.couchbase.com","xcp-s237.sc.couchbase.com","xcp-s238.sc.couchbase.com","172.23.104.33",
    "172.23.121.82","xcp-s413.sc.couchbase.com","172.23.120.34","172.23.104.27","172.23.107.96","172.23.104.49","172.23.104.101",
    "xcp-s304.sc.couchbase.com","xcp-s123.sc.couchbase.com","mcp-s232.sc.couchbase.com","xcp-s724.sc.couchbase.com","mcp-s734.sc.couchbase.com",
    "xcp-s622.sc.couchbase.com","xcp-s720.sc.couchbase.com","xcp-s707.sc.couchbase.com","xcp-s411.sc.couchbase.com","xcp-s608.sc.couchbase.com",
    "xcp-s121.sc.couchbase.com","xcp-s120.sc.couchbase.com","172.23.104.15","172.23.97.206","172.23.108.127","172.23.105.141","172.23.122.76",
    "xcp-s725.sc.couchbase.com","172.23.124.51","xcp-s004.sc.couchbase.com","172.23.108.4","172.23.108.7","172.23.109.145","172.23.110.9",
    "xcp-s021.sc.couchbase.com","172.23.110.11","172.23.108.230","172.23.106.68","172.23.105.222","172.23.107.222","172.23.104.8","172.23.104.58",
    "172.23.120.26","172.23.120.149","172.23.110.13","xcp-s607.sc.couchbase.com","kvm-s713.sc.couchbase.com","172.23.110.14","172.23.110.15",
    "172.23.110.16","172.23.110.17","172.23.110.18","172.23.106.113","172.23.104.72","xcp-s425.sc.couchbase.com","172.23.110.21","172.23.110.22",
    "172.23.110.23","172.23.110.24","172.23.110.25","172.23.110.26","172.23.110.27","172.23.110.29","172.23.110.19","172.23.110.31","172.23.110.32",
    "172.23.99.184","172.23.97.43","xcp-s111.sc.couchbase.com","xcp-s817.sc.couchbase.com","172.23.124.19","xcp-sb33.sc.couchbase.com","172.23.104.12"]
    
    qemobilehosts = ["172.23.107.70","xcp-s619.sc.couchbase.com","xcp-s617.sc.couchbase.com","172.23.105.43","172.23.105.125","172.23.123.241",
    "172.23.96.59","172.23.110.28","172.23.110.30","xcp-s614.sc.couchbase.com"]

    qesdkhosts = ["172.23.121.82","172.23.107.96","172.23.110.9","172.23.99.184"]
    #,"172.23.97.234"]

    dynvmhosts =["xcp-s827.sc.couchbase.com","xcp-sb37.sc.couchbase.com","xcp-sb31.sc.couchbase.com","xcp-sb34.sc.couchbase.com",
        "xcp-sb36.sc.couchbase.com","xcp-s215.sc.couchbase.com","xcp-s511.sc.couchbase.com","xcp-sd19.sc.couchbase.com"] 

    # 140 hosts as on 04/30/2021 - Ref: http://nagios.corp.couchbase.com/nagios/cgi-bin/status.cgi?hostgroup=qe-hosts&style=hostdetail&hoststatustypes=2&limit=250
    qehosts_cbit_nagios=["xcp-s004.sc.couchbase.com","xcp-s006.sc.couchbase.com","xcp-s007.sc.couchbase.com","xcp-s009.sc.couchbase.com",
    "xcp-s020.sc.couchbase.com","xcp-s103.sc.couchbase.com","xcp-s104.sc.couchbase.com","xcp-s104old.sc.couchbase.com","xcp-s105.sc.couchbase.com",
    "xcp-s106.sc.couchbase.com","xcp-s111.sc.couchbase.com","xcp-s114.sc.couchbase.com","xcp-s115.sc.couchbase.com","xcp-s119.sc.couchbase.com",
    "xcp-s120.sc.couchbase.com","xcp-s121.sc.couchbase.com","xcp-s123.sc.couchbase.com","xcp-s127.sc.couchbase.com","xcp-s129.sc.couchbase.com",
    "xcp-s130.sc.couchbase.com","xcp-s205.sc.couchbase.com","xcp-s207.sc.couchbase.com","xcp-s214.sc.couchbase.com","xcp-s216.sc.couchbase.com",
    "xcp-s222.sc.couchbase.com","xcp-s223.sc.couchbase.com","xcp-s224.sc.couchbase.com","xcp-s225.sc.couchbase.com","xcp-s228.sc.couchbase.com",
    "xcp-s229.sc.couchbase.com","xcp-s237.sc.couchbase.com","xcp-s238.sc.couchbase.com","xcp-s239.sc.couchbase.com","xcp-s240.sc.couchbase.com",
    "xcp-s242.sc.couchbase.com","xcp-s304.sc.couchbase.com","xcp-s313.sc.couchbase.com","xcp-s316.sc.couchbase.com","xcp-s319.sc.couchbase.com","xcp-s330.sc.couchbase.com",
    "xcp-s414.sc.couchbase.com","xcp-s418.sc.couchbase.com","xcp-s425.sc.couchbase.com","xcp-s436.sc.couchbase.com","xcp-s440.sc.couchbase.com",
    "xcp-s509.sc.couchbase.com","xcp-s512.sc.couchbase.com","xcp-s514.sc.couchbase.com","xcp-s608.sc.couchbase.com","xcp-s621-mgt.sc.couchbase.com",
    "xcp-s621.sc.couchbase.com","xcp-s622.sc.couchbase.com","xcp-s623.sc.couchbase.com","xcp-s637.sc.couchbase.com","xcp-s638.sc.couchbase.com","xcp-s706.sc.couchbase.com",
    "xcp-s707.sc.couchbase.com","xcp-s718.sc.couchbase.com","xcp-s719.sc.couchbase.com","xcp-s720.sc.couchbase.com","xcp-s724.sc.couchbase.com",
    "xcp-s725.sc.couchbase.com","xcp-s726.sc.couchbase.com","xcp-s727.sc.couchbase.com","xcp-s728.sc.couchbase.com","xcp-s729.sc.couchbase.com",
    "xcp-s730.sc.couchbase.com","xcp-s731.sc.couchbase.com","xcp-s732.sc.couchbase.com","xcp-s733.sc.couchbase.com","xcp-s802-nyx06-s802.sc.couchbase.com","xcp-s802.sc.couchbase.com",
    "xcp-s811.sc.couchbase.com","xcp-s812.sc.couchbase.com","xcp-s817.sc.couchbase.com","xcp-s822.sc.couchbase.com","xcp-s823.sc.couchbase.com",
    "xcp-s825.sc.couchbase.com","xcp-s826.sc.couchbase.com","xcp-s827.sc.couchbase.com","xcp-s830.sc.couchbase.com","xcp-s831.sc.couchbase.com",
    "xcp-s838.sc.couchbase.com","xcp-s840.sc.couchbase.com","xcp-sa15.sc.couchbase.com","xcp-sa16.sc.couchbase.com","xcp-sa17.sc.couchbase.com",
    "xcp-sa18.sc.couchbase.com","xcp-sa19.sc.couchbase.com","xcp-sa20.sc.couchbase.com","xcp-sa21.sc.couchbase.com","xcp-sa22.sc.couchbase.com",
    "xcp-sa23.sc.couchbase.com","xcp-sa24.sc.couchbase.com","xcp-sa25.sc.couchbase.com","xcp-sa26.sc.couchbase.com","xcp-sa27.sc.couchbase.com",
    "xcp-sa28.sc.couchbase.com","xcp-sb28.sc.couchbase.com","xcp-sb29.sc.couchbase.com","xcp-sb30.sc.couchbase.com","xcp-sb31.sc.couchbase.com",
    "xcp-sb32.sc.couchbase.com","xcp-sb33.sc.couchbase.com","xcp-sb34.sc.couchbase.com","xcp-sb35.sc.couchbase.com","xcp-sb36.sc.couchbase.com",
    "xcp-sb37.sc.couchbase.com","xcp-sc07.sc.couchbase.com","xcp-sc08.sc.couchbase.com","xcp-sc09.sc.couchbase.com","xcp-sc10.sc.couchbase.com",
    "xcp-sc11.sc.couchbase.com","xcp-sc12.sc.couchbase.com","xcp-sc13.sc.couchbase.com","xcp-sc14.sc.couchbase.com","xcp-sc15.sc.couchbase.com",
    "xcp-sc16.sc.couchbase.com","xcp-sc20.sc.couchbase.com","xcp-sc21.sc.couchbase.com","xcp-sc22.sc.couchbase.com","xcp-sc23.sc.couchbase.com",
    "xcp-sc24.sc.couchbase.com","xcp-sc25.sc.couchbase.com","xcp-sc26.sc.couchbase.com","xcp-sc27.sc.couchbase.com","xcp-sc28.sc.couchbase.com",
    "xcp-sc29.sc.couchbase.com","xcp-sd25.sc.couchbase.com","xcp-sd29.sc.couchbase.com","xcp-sd30.sc.couchbase.com","xcp-sd31.sc.couchbase.com",
    "xcp-sd32.sc.couchbase.com","xcp-sd33.sc.couchbase.com","xcp-sd34.sc.couchbase.com","xcp-sd35.sc.couchbase.com","xcp-sd36.sc.couchbase.com",
    "xcp-sd37.sc.couchbase.com","xcp-sd38.sc.couchbase.com","xcp-sd39.sc.couchbase.com",]    
    #,"xcp-s731.sc.couchbase.com"
    grandvms=0
    i = 1
    parser = argparse.ArgumentParser()
    parser.add_argument("-x","--xenurl", default="default", help="[default] xenserver host url")
    parser.add_argument("-u","--username", default="root", help="[root] xenserver host username")
    parser.add_argument("-p","--userpwd", help="xenserver host user pwd")
    args = parser.parse_args()

    username = args.username
    password = args.userpwd
    if not password:
        password = os.environ.get('xenhost_password')
        if not password:
            print("Error: -p <password> argument or xenhost_password= environment variable is not set!")
            exit(1)
    hosts=args.xenurl
    if args.xenurl == "default":
        #hosts=defaulthosts
        
        #allhosts = []
        #allhosts.extend(qeserverhosts)
        #allhosts.extend(qemobilehosts)
        #allhosts.extend(qesdkhosts)
        #allhosts.extend(dynvmhosts)
        #hosts=allhosts
        hosts = qehosts_cbit_nagios
    elif args.xenurl == "qeserver":
        hosts=qeserverhosts 
    elif args.xenurl == "qemobile":
        hosts=qemobilehosts
    elif args.xenurl == "qesdk":
        hosts=qesdkhosts 
    elif args.xenurl == "dynvm":
        hosts=dynvmhosts                 
    else:
        hosts=args.xenurl.split(",")

    count=len(hosts)
    print("\nXen Server hosts count: "+str(count)+", list:"+str(hosts)+"\n")
    print("-----------------------------------------------------------")
    print("host,host_ip,host_label,host_manufacturer,host_product_name,host_xen_version,host_patch_count,host_cpu_count,host_cpu_socket_count,xen_vcpu_count_total,xen_vcpu_count_free," 
            "xen_memory_total_gb,xen_memory_free_gb,vm_count,vm_name,vm_state,vm_vcpus,vm_memory_gb,vm_networkinfo,"
            "os_version_distro,os_version_naame,os_version_uname")
    print("-----------------------------------------------------------")
    csvout = open("xen_hosts_info.csv", "w")
    csvout.write("host,host_ip,host_label,host_manufacturer,host_product_name,host_xen_version,host_patch_count,host_cpu_count,host_cpu_socket_count,xen_vcpu_count_total,xen_vcpu_count_free," 
            "xen_memory_total_gb,xen_memory_free_gb,vm_count,vm_name,vm_state,vm_vcpus,vm_memory_gb,vm_networkinfo,"
            "os_version_distro,os_version_naame,os_version_uname")
            
    for host in hosts:
        url = "http://"+host
        

        print("\n*** HOST#"+str(i)+"/"+str(count)+" : " +url+" ***")
        try:
            session = XenAPI.Session(url)
            session.xenapi.login_with_password(username, password)
            main(session,host,csvout, username, password)
            session.logout()
        except Exception as e:
            print("{}: {}".format(host,e))
            csvout.write("\n{},{}".format(host, e))
            csvout.flush()
        i=i+1

    print("Total VMs={}".format(grandvms))  
    csvout.write("\n{},,,,,,,,,,,,,{}\n".format(i-1, grandvms))    
    csvout.close()
    
    