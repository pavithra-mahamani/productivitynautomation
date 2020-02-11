import XenAPI
import sys
import argparse
import json
import time
import datetime
import logging
log = logging.getLogger(__name__)
logging.info("dynxenvms")
print("*** Dynamic VMs ***")

def usage(err=None):
    print("""\
Usage Syntax: dynxenvms -h or options

Examples:
 python dynxenvms.py -h
 python dynxenvms.py -x xenserver -u root -p pwd -c vmname -n count"
""")
    sys.exit(0)
def setLogLevel(log_level):
    if log_level and log_level.lower() == 'info':
        log.setLevel(logging.INFO)
    elif log_level and log_level.lower() == 'warning':
        log.setLevel(logging.WARNING)
    elif log_level and log_level.lower() == 'debug':
        log.setLevel(logging.DEBUG)
    elif log_level and log_level.lower() == 'critical':
        log.setLevel(logging.CRITICAL)
    elif log_level and log_level.lower() == 'fatal':
        log.setLevel(logging.FATAL)
    else:
        log.setLevel(logging.NOTSET)

def list_vms(session, options):
    vm_count=0
    vms = session.xenapi.VM.get_all()
    log.info("Server has {} VM objects (this includes templates):".format(len(vms)))
    log.info("-----------------------------------------------------------")
    log.info("S.No.,VMname,PowerState,Vcpus,MaxMemory,Networkinfo,Description")
    log.info("-----------------------------------------------------------")

    for vm in vms:

        record = session.xenapi.VM.get_record(vm)
        if not (record["is_a_template"]) and not (record["is_control_domain"]):
            vm_count = vm_count + 1
            name = record["name_label"]
            name_description = record["name_description"]
            uuid = record["uuid"]
            power_state = record["power_state"]
            vcpus = record["VCPUs_max"]
            memory_static_max = record["memory_static_max"]
            hostVIFs = record['VIFs']
            if (record["power_state"] != 'Halted'):
                ipRef = session.xenapi.VM_guest_metrics.get_record(record['guest_metrics'])
                networkinfo = ','.join([str(elem) for elem in ipRef['networks'].values()])
            else:
                networkinfo = 'N/A'
            log.info(str(
                vm_count) + "," + name + "," + power_state + "," + vcpus + "," + memory_static_max +
                  "," + networkinfo +", "+name_description)

    log.info("Server has {} VM objects and {} templates.".format(vm_count, len(vms)-vm_count))


def create_vm(session, options, new_vm_name):
    log.info("\n--- Creating VM: " + new_vm_name + " using " + options.template)
    pifs = session.xenapi.PIF.get_all_records()
    lowest = None
    for pifRef in pifs.keys():
        if (lowest is None) or (pifs[pifRef]['device'] < pifs[lowest]['device']):
            lowest = pifRef
    log.debug("Choosing PIF with device: {}".format(pifs[lowest]['device']))
    # List all the VM objects
    vms = session.xenapi.VM.get_all_records()
    log.debug("Server has {} VM objects (this includes templates)".format(len(vms)))

    templates = []
    all_templates = []
    for vm in vms:
        record = vms[vm]
        ty = "VM"
        if record["is_a_template"]:
            ty = "Template"
            all_templates.append(vm)
            # Look for a given template
            if record["name_label"].startswith(options.template):
                templates.append(
                    vm)  #  log.info("  Found %8s with name_label = %s" % (ty,
                # record["name_label"]))

    log.debug("Server has {} Templates and {} VM objects.".format(
        len(all_templates), (len(vms) - len(all_templates))))

    log.debug("Choosing a " + options.template + " template to clone")
    if not templates:
        log.error("Could not find any " + options.template + " templates. Exiting.")
        sys.exit(1)

    template = templates[0]
    log.debug("  Selected template: {}".format(session.xenapi.VM.get_name_label(template)))
    log.debug("Installing new VM from the template")
    vm = session.xenapi.VM.clone(template, new_vm_name)

    network = session.xenapi.PIF.get_network(lowest)
    log.debug("Chosen PIF is connected to network: {}".format(session.xenapi.network.get_name_label(
        network)))
    vifs = session.xenapi.VIF.get_all()
    log.debug(("Number of VIFs=" + str(len(vifs))))
    for i in range(len(vifs)):
        vmref = session.xenapi.VIF.get_VM(vifs[i])
        a_vm_name = session.xenapi.VM.get_name_label(vmref)
        #  log.info((str(i)+"."+session.xenapi.network.get_name_label(session.xenapi.VIF.get_network(
        #    vifs[i]))+" "+a_vm_name)
        if (a_vm_name == new_vm_name):
            session.xenapi.VIF.move(vifs[i], network)

    log.debug("Adding non-interactive to the kernel commandline")
    session.xenapi.VM.set_PV_args(vm, "non-interactive")
    log.debug("Choosing an SR to instantiate the VM's disks")
    pool = session.xenapi.pool.get_all()[0]
    default_sr = session.xenapi.pool.get_default_SR(pool)
    default_sr = session.xenapi.SR.get_record(default_sr)
    log.debug("Choosing SR: {} (uuid {})".format(default_sr['name_label'], default_sr['uuid']))
    log.debug("Asking server to provision storage from the template specification")
    description = new_vm_name + " from " + template + " on " + str(
        datetime.datetime.utcnow())
    session.xenapi.VM.set_name_description(vm, description)
    session.xenapi.VM.provision(vm)
    log.info("Starting VM")
    session.xenapi.VM.start(vm, False, True)
    log.debug("  VM is booting")

    log.debug("Waiting for the installation to complete")

    # Here we poll because we don't generate events for metrics objects currently

    def read_os_name(a_vm):
        vgm = session.xenapi.VM.get_guest_metrics(a_vm)
        try:
            os = session.xenapi.VM_guest_metrics.get_os_version(vgm)
            if "name" in os.keys():
                return os["name"]
            return None
        except:
            return None

    def read_ip_address(a_vm):
        vgm = session.xenapi.VM.get_guest_metrics(a_vm)
        try:
            os = session.xenapi.VM_guest_metrics.get_networks(vgm)
            if "0/ip" in os.keys():
                return os["0/ip"]
            return None
        except:
            return None

    while read_os_name(vm) is None:
        time.sleep(1)
    vm_os_name = read_os_name(vm)
    log.info("VM OS name: {}".format(vm_os_name))
    while read_ip_address(vm) is None:
        time.sleep(1)
    vm_ip_addr = read_ip_address(vm)
    log.info("VM IP: {}".format(vm_ip_addr))
    return vm_ip_addr, vm_os_name

def create_vms(session, options):
    vm_names = options.create_vm_names.split(",")
    index = 1
    new_vms_info = {}
    for i in range(len(vm_names)):
        if int(options.number_of_vms)>1:
            for k in range(int(options.number_of_vms)):
                vm_name = vm_names[i] + str(k+1)
                vm_ip, vm_os = create_vm(session, options, vm_name)
                new_vms_info[vm_name] = vm_ip
                index = index+1
        else:
            vm_ip, vm_os = create_vm(session, options, vm_names[i])
            new_vms_info[vm_names[i]] = vm_ip
            index = index + 1
    return new_vms_info

def delete_vm(session, vm_name):
    log.info("Deleting VM: "+ vm_name)
    vm = session.xenapi.VM.get_by_name_label(vm_name)
    for j in range(len(vm)):
        record = session.xenapi.VM.get_record(vm[j])
        power_state = record["power_state"]
        if power_state != 'Halted':
            session.xenapi.VM.shutdown(vm[j])
        session.xenapi.VM.destroy(vm[j])

def delete_vms(session, options):
    vm_names = options.delete_vm_names.split(",")
    for i in range(len(vm_names)):
        if int(options.number_of_vms)>1:
            for k in range(int(options.number_of_vms)):
                delete_vm(session, vm_names[i] + str(k+1))
        else:
            delete_vm(session, vm_names[i])

def parse_arguments():
    log.debug("Parsing arguments")
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xenhost", default="172.23.106.113", help="[default] "
                                                                          "dynamic xenserver "
                                                                          "host IP/name")
    parser.add_argument("-u", "--username", default="root", help="[root] xenserver host username")
    parser.add_argument("-p", "--userpwd", help="xenserver host user pwd")
    parser.add_argument("-t", "--template", default="tmpl-cnt7.7",
                        help="Enter the VM template name")
    parser.add_argument("-c", "--create_vm", dest="create_vm_names",
                        help="To create vms with given names")
    parser.add_argument("-d", "--delete_vm", dest="delete_vm_names", help="To delete VMs")
    parser.add_argument("-n", "--number_of_vms", dest="number_of_vms", default="1",
                        help="Count of VMs with "
                             "given create or delete VM prefix names")
    parser.add_argument("-l", "--log-level", dest="loglevel", default="INFO",
                        help="e.g -l info,warning,error")
    options = parser.parse_args()
    if not options.userpwd:
        log.error("No xenserver {} user -p password given!".format(options.username))
        usage()
        sys.exit(1)
    #if options.create_vm_names == 'prod-qa-auto':
    #    options.create_vm_names += "-"+datetime.datetime.utcnow().strftime("-%m%d%Y-%H%M%S")
    return options

def main():
    options = parse_arguments()
    setLogLevel(options.loglevel)
    log.debug("\nXen Server host: " + options.xenhost + "\n")

    url = "http://" + options.xenhost
    session = XenAPI.Session(url)
    try:
        session.xenapi.login_with_password(options.username, options.userpwd)
    except XenAPI.Failure as f:
        log.error("Failed to acquire a session: %s" % f.details)
        sys.exit(1)

    try:
        if options.create_vm_names:
            new_vms = create_vms(session, options)
            log.info(new_vms)
        elif options.delete_vm_names:
            delete_vms(session, options)
        else:
            list_vms(session, options)
    except Exception as e:
        log.error(str(e))
        raise
    finally:
        session.logout()


if __name__ == "__main__":
    main()

