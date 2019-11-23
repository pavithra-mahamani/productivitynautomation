import XenAPI
import sys
import argparse
import json

index=1
def main(session,host):
    global index
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

     
    #,"xcp-s731.sc.couchbase.com"
    grandvms=0
    i = 1
    parser = argparse.ArgumentParser()
    parser.add_argument("-x","--xenurl", default="default", help="[default] xenserver host url")
    parser.add_argument("-u","--username", default="root", help="[root] xenserver host username")
    parser.add_argument("-p","--userpwd", help="xenserver host user pwd")
    args = parser.parse_args()
    #print args.xenurl


    hosts=args.xenurl

    if args.xenurl == "default":
        #hosts=defaulthosts
        allhosts = []
        allhosts.extend(qeserverhosts)
        allhosts.extend(qemobilehosts)
        allhosts.extend(qesdkhosts)
        hosts=allhosts
    elif args.xenurl == "qeserver":
        hosts=qeserverhosts 
    elif args.xenurl == "qemobile":
        hosts=qemobilehosts
    elif args.xenurl == "qesdk":
        hosts=qesdkhosts             
    else:
        hosts=args.xenurl.split(",")

    count=len(hosts)
    print("\nXen Server hosts count: "+str(count)+", list:"+str(hosts)+"\n")
    print("-----------------------------------------------------------")
    print("S.No.,Xenhost,VMname,PowerState,Vcpus,MaxMemory,Networkinfo")
    print("-----------------------------------------------------------")
    for host in hosts:
        url = "http://"+host
        username = args.username #"root"
        password = args.userpwd

        #print("\n*** HOST#"+str(i)+"/"+str(count)+" : " +url+" ***")
        try:
            session = XenAPI.Session(url)
            session.xenapi.login_with_password(username, password)
            main(session,host)
            session.logout()
        except Exception as e:
            print(host+" :")
            print(e)
        i=i+1
    #print("Total VMs="+grandvms)
    