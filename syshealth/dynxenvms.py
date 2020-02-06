import XenAPI
import sys
import argparse
import json
import time

index=1

def list_vms(session):
    global index
    vms = session.xenapi.VM.get_all()
    # print ("Server has %d VM objects (this includes templates):" % (len(vms)))

    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        #print("vm record:",record)
        if not (record["is_a_template"]) and not (record["is_control_domain"]):
                #and (record["power_state"] != 'Halted'):
            name = record["name_label"]
            name_description = record["name_description"]
            uuid = record["uuid"]
            power_state = record["power_state"]
            vcpus = record["VCPUs_max"]
            memory_static_max = record["memory_static_max"]
            hostVIFs = record['VIFs']
            # hostaddress = record['host.address']
            ipRef = session.xenapi.VM_guest_metrics.get_record(record['guest_metrics'])
            # print(ipRef)
            # ipAdd0 = ipRef['networks']['0/ip']
            networkinfo = ','.join([str(elem) for elem in ipRef['networks'].values()])
            # print("VM#"+str(index)+","+name+","+ipAdd0+","+power_state+","+vcpus+",
            # "+memory_static_max+","+name_description)
            print(str(
                index) + "," + name + "," + power_state + "," + vcpus + "," + memory_static_max + "," + networkinfo)
            # print("ipAdd0="+ipAdd0)
            index = index + 1

def main(options):
    print("\nXen Server host: " + options.xenhost + "\n")
    print("-----------------------------------------------------------")
    print("S.No.,VMname,PowerState,Vcpus,MaxMemory,Networkinfo")
    print("-----------------------------------------------------------")

    url = "http://" + options.xenhost
    try:
        session = XenAPI.Session(url)
        session.xenapi.login_with_password(options.username, options.userpwd)

        if options.createvm:
            create_vm(session, options)
        else:
            list_vms(session)

        session.logout()
    except Exception as e:
        print(options.xenhost + " :")
        print(e)

def create_vm(session, options):
    fmt = "%8s  %20s  %5s  %s"
    session.xenapi.event.register(["*"])

    print("Creating VM using " + options.template)
    vm = session.xenapi.VM.get_by_name_label(options.template)
    print ("vm[0]="+vm[0])
    task = session.xenapi.Async.VM.clone(vm[0], "test_clone_vm")
    while session.xenapi.task.get_status(task) == "pending":
        progress = session.xenapi.task.get_progress(task)
        print(".")
        time.sleep(1)
    print(task)

    while True:
        try:
            for event in session.xenapi.event.next():
                name = "(unknown)"
                if "snapshot" in event.keys():
                    snapshot = event["snapshot"]
                    if "name_label" in snapshot.keys():
                        name = snapshot["name_label"]
                print fmt % (event['id'], event['class'], event['operation'], name)
        except XenAPI.Failure, e:
            if e.details == ["EVENTS_LOST"]:
                print "Caught EVENTS_LOST; should reregister"

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-x","--xenhost", default="172.23.106.113", help="[default] "
                                                                               "dynamic xenserver "
                                                                        "host IP/name")
    parser.add_argument("-u","--username", default="root", help="[root] xenserver host username")
    parser.add_argument("-p","--userpwd", help="xenserver host user pwd")
    parser.add_argument("-t", "--template", default="CentOS 7", help="Enter the VM template name")
    parser.add_argument("-c", "--createvm", action="store_true", help="Use -c option to create "
                                                                      "vm")

    options = parser.parse_args()
    main(options)

