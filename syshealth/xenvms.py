import XenAPI
import sys
import argparse



def main(session):

    vms = session.xenapi.VM.get_all()
    print ("Server has %d VM objects (this includes templates):" % (len(vms)))

    index=1
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        #print("vm record:",record)
        if not (record["is_a_template"]) and not (record["is_control_domain"]):
            name = record["name_label"]
            name_description = record["name_description"]
            uuid = record["uuid"]
            power_state = record["power_state"]
            vcpus = record["VCPUs_max"]
            memory_static_max = record["memory_static_max"]
            print("VM#"+str(index)+","+name+","+power_state+","+vcpus+","+memory_static_max+","+name_description)
            index=index+1
            #grandvms+=index


if __name__ == "__main__":

    defaulthosts = ["xcp-s418.sc.couchbase.com","xcp-s823.sc.couchbase.com","xcp-s823.sc.couchbase.com","xcp-s719.sc.couchbase.com",
             "xcp-s440.sc.couchbase.com","xcp-s121.sc.couchbase.com","xcp-s021.sc.couchbase.com","xcp-s022.sc.couchbase.com",
             "xcp-s411.sc.couchbase.com","172.23.110.17","xcp-sa28.sc.couchbase.com",
             "xcp-s123.sc.couchbase.com","xcp-s436.sc.couchbase.com","xcp-s606.sc.couchbase.com"]
    #,"xcp-s731.sc.couchbase.com"
    grandvms=0
    i = 1
    parser = argparse.ArgumentParser()
    parser.add_argument("-x","--xenurl", help="[default] xenserver host url")
    parser.add_argument("-u","--username", help="[root] xenserver host username")
    parser.add_argument("-p","--userpwd", help="xenserver host user pwd")
    args = parser.parse_args()
    print args.xenurl


    hosts=args.xenurl

    if args.xenurl == "default":
        hosts=defaulthosts
    else:
        hosts=args.xenurl.split(",")

    print("\nXen Server hosts ist:"+str(hosts)+"\n")
    for host in hosts:
        url = "http://"+host
        username = args.username #"root"
        password = args.userpwd

        print("\n*** HOST#"+str(i)+": " +url+" ***")
        try:
            session = XenAPI.Session(url)
            session.xenapi.login_with_password(username, password)
            main(session)
        except Exception as e:
            print(e)
        i=i+1
    #print("Total VMs="+grandvms)
