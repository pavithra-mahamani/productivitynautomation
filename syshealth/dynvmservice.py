import urllib

import XenAPI
import sys
import argparse
import json
import time
import datetime
from flask import Flask, request
import configparser
from couchbase.bucket import Bucket
from couchbase.cluster import Cluster
from couchbase.cluster import PasswordAuthenticator
import threading

import logging
log = logging.getLogger(__name__)
logging.info("dynxenvms")
print("*** Dynamic VMs ***")
app = Flask(__name__)

CONFIG_FILE='.dynvmservice.ini'
MAX_EXPIRY_MINUTES=1440
TIMEOUT_SECS=300

@app.route("/showall")
def showall_service():
    return perform_service(service_name='listvms')

@app.route('/getavailablecount/<string:os>')
def getavailable_count_service(os):
    #TBD: calculate the actual cpu,memory,disk usaged in the xenhosts
    count=15
    return str(count)


#/getservers/username?count=number&os=centos&ver=6&expiresin=30
@app.route('/getservers/<string:username>')
def getservers_service(username):
    if request.args.get('count'):
        vm_count = int(request.args.get('count'))
    else:
        vm_count = 1
    os_name = request.args.get('os')
    if request.args.get('cpus'):
        cpus_count = request.args.get('cpus')
    else:
        cpus_count = "default"

    if request.args.get('mem'):
        mem = request.args.get('mem')
    else:
        mem = "default"

    if request.args.get('expiresin'):
        exp = int(request.args.get('expiresin'))
    else:
        exp = MAX_EXPIRY_MINUTES
    if request.args.get('format'):
        output_format = request.args.get('format')
    else:
        output_format = "servermanager"
    return perform_service(1,'createvm', os_name, username, vm_count, cpus=cpus_count,
                           maxmemory=mem, expiry_minutes=exp, output_format=output_format)

#/releaseservers/{username}
@app.route('/releaseservers/<string:username>/<string:available>')
@app.route('/releaseservers/<string:username>')
def releaseservers_service(username):
    if request.args.get('count'):
        vm_count = int(request.args.get('count'))
    else:
        vm_count = 1
    os_name = request.args.get('os')
    return perform_service(1,'deletevm', os_name, username, vm_count)

def perform_service(xen_host_ref=1, service_name='list_vms', os="centos", vm_prefix_names="",
                                                                number_of_vms=1, cpus="default",
                    maxmemory="default", expiry_minutes=MAX_EXPIRY_MINUTES,
                    output_format="servermanager"):
    xen_host = get_xen_host(xen_host_ref, os)
    #xen_host = get_all_xen_hosts(os)[0]
    url = "http://" + xen_host['host.name']
    log.debug("\nXen Server host: " + xen_host['host.name'] + "\n")
    try:
        session = XenAPI.Session(url)
        session.xenapi.login_with_password(xen_host['host.user'], xen_host['host.password'])
    except XenAPI.Failure as f:
        error = "Failed to acquire a session: {}".format(f.details)
        log.error(error)
        return error

    options = argparse.ArgumentParser()
    log.info("Getting template "+ os+'.template')
    template = xen_host[os+'.template']
    try:
        if service_name == 'createvm':
            log.debug("Creating from "+template+" :" +vm_prefix_names + ", cpus: "+cpus+", "
                                                                                        "memory: "
                                                                                        "" +
                      maxmemory)
            new_vms, list_of_vms = create_vms(session, os, template, vm_prefix_names,
                                              number_of_vms, cpus,
                                 maxmemory, expiry_minutes)
            log.info(new_vms)
            log.info(list_of_vms)
            if output_format == 'json':
                return new_vms
            else:
                return str(list_of_vms)
        elif service_name == 'deletevm':
            return delete_vms(session, vm_prefix_names, number_of_vms)
        elif service_name == 'listvm':
            return list_given_vm_set_details(session, vm_prefix_names, number_of_vms)
        elif service_name == 'listvms':
            return list_vms(session)
        else:
            list_vms(session)
    except Exception as e:
        log.error(str(e))
        raise
    finally:
        session.logout()

def get_config(name):
    config = read_config()
    section_ref=1
    all_config = []
    xen_host = {}
    for section in config.sections():
        if section.startswith(name):
            section_config = {}
            for key in config.keys():
                section_config[key] = config.get(name + str(section_ref), key)
            all_config.append(section_config)
            section_ref += 1

    return all_config

def get_all_xen_hosts(os='centos'):
    config = read_config()
    xen_host_ref=1
    all_xen_hots = []
    xen_host = {}
    for section in config.sections():
        if section.startswith('xenhost'):
            xen_host = {}
            get_xen_values(config, xen_host_ref, os)
            all_xen_hots.append(xen_host)
            xen_host_ref += 1

    return all_xen_hots

def get_xen_host(xen_host_ref=1,os='centos'):
    config = read_config()
    return get_xen_values(config, xen_host_ref, os)

def get_xen_values(config, xen_host_ref, os):
    xen_host = {}
    xen_host["host.name"] = config.get('xenhost' + str(xen_host_ref), 'host.name')
    xen_host["host.user"] = config.get('xenhost' + str(xen_host_ref), 'host.user')
    xen_host["host.password"] = config.get('xenhost' + str(xen_host_ref), 'host.password')
    xen_host[os + ".template"] = config.get('xenhost' + str(xen_host_ref), os + '.template')
    return xen_host

def read_config():
    config = configparser.RawConfigParser()
    config.read(CONFIG_FILE)
    log.info(config.sections())
    return config

def usage(err=None):
    print("""\
Usage Syntax: dynxenvms -h or options

Examples:
 python dynxenvms.py -h
 python dynxenvms.py -x xenserver -u root -p pwd -c vmname -n count"
""")
    sys.exit(0)
def setLogLevel(log_level='info'):
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


def list_vms(session):
    vm_count=0
    vms = session.xenapi.VM.get_all()
    log.info("Server has {} VM objects (this includes templates):".format(len(vms)))
    log.info("-----------------------------------------------------------")
    log.info("S.No.,VMname,PowerState,Vcpus,MaxMemory,Networkinfo,Description")
    log.info("-----------------------------------------------------------")

    vm_details = []
    for vm in vms:
        record = session.xenapi.VM.get_record(vm)
        if not (record["is_a_template"]) and not (record["is_control_domain"]):
            log.info(record)
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

            vm_info = {}
            vm_info['name'] = name
            vm_info['power_state'] = power_state
            vm_info['vcpus'] = vcpus
            vm_info['memory_static_max'] = memory_static_max
            vm_info['networkinfo'] = networkinfo
            vm_info['name_description'] = name_description
            vm_details.append(vm_info)
            log.info(vm_info)

    log.info("Server has {} VM objects and {} templates.".format(vm_count, len(vms)-vm_count))
    log.debug(vm_details)
    return json.dumps(vm_details, indent=2, sort_keys=True)

def list_vm_details(session, vm_name):
    vm = session.xenapi.VM.get_by_name_label(vm_name)
    if len(vm)>0:
        record = session.xenapi.VM.get_record(vm[0])
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
        log.info(vm_name + "," + power_state + "," + vcpus + "," + memory_static_max +
              "," + networkinfo +", "+name_description)


def create_vms(session, os, template, vm_prefix_names, number_of_vms=1, cpus="default",
                    maxmemory="default", expiry_minutes=MAX_EXPIRY_MINUTES):
    vm_names = vm_prefix_names.split(",")
    index = 1
    new_vms_info = {}
    list_of_vms = []
    for i in range(len(vm_names)):
        if int(number_of_vms)>1:
            for k in range(int(number_of_vms)):
                vm_name = vm_names[i] + str(k+1)
                vm_ip, vm_os, error = create_vm(session, os, template, vm_name, cpus, maxmemory,
                                                expiry_minutes)
                new_vms_info[vm_name] = vm_ip
                list_of_vms.append(vm_ip)
                if error:
                    new_vms_info[vm_name+"_error"] = error
                    list_of_vms.append(error)

                index = index+1
        else:
            vm_ip, vm_os, error = create_vm(session, os, template, vm_names[i], cpus, maxmemory,
                                            expiry_minutes)
            new_vms_info[vm_names[i]] = vm_ip
            list_of_vms.append(vm_ip)
            if error:
                new_vms_info[vm_names[i] + "_error"] = error
                list_of_vms.append(error)
            index = index + 1
    return new_vms_info, list_of_vms

def create_vm(session, os_name, template, new_vm_name, cpus="default",
                    maxmemory="default", expiry_minutes=MAX_EXPIRY_MINUTES):
    error = ''
    vm_os_name = ''
    vm_ip_addr = ''
    prov_start_time = time.time()
    try:
        log.info("\n--- Creating VM: " + new_vm_name + " using " + template)
        pifs = session.xenapi.PIF.get_all_records()
        lowest = None
        for pifRef in pifs.keys():
            if (lowest is None) or (pifs[pifRef]['device'] < pifs[lowest]['device']):
                lowest = pifRef
        log.debug("Choosing PIF with device: {}".format(pifs[lowest]['device']))
        ref = lowest
        mac = pifs[ref]['MAC']
        device = pifs[ref]['device']
        mode = pifs[ref]['ip_configuration_mode']
        IP = pifs[ref]['IP']
        netmask = pifs[ref]['IP']
        gateway = pifs[ref]['gateway']
        DNS = pifs[ref]['DNS']
        log.debug(mac+","+device+","+mode+","+IP+","+netmask+","+gateway+","+DNS)
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
                if record["name_label"].startswith(template):
                    templates.append(
                        vm)  #  log.info("  Found %8s with name_label = %s" % (ty,
                    # record["name_label"]))

        log.debug("Server has {} Templates and {} VM objects.".format(
            len(all_templates), (len(vms) - len(all_templates))))

        log.debug("Choosing a " + template + " template to clone")
        if not templates:
            log.error("Could not find any " + template + " templates. Exiting.")
            sys.exit(1)

        template_ref = templates[0]
        log.debug("  Selected template: {}".format(session.xenapi.VM.get_name_label(template_ref)))
        log.debug("Installing new VM from the template")
        vm = session.xenapi.VM.clone(template_ref, new_vm_name)

        network = session.xenapi.PIF.get_network(lowest)
        log.debug("Chosen PIF is connected to network: {}".format(session.xenapi.network.get_name_label(
            network)))
        vifs = session.xenapi.VIF.get_all()
        log.debug(("Number of VIFs=" + str(len(vifs))))
        for i in range(len(vifs)):
            vmref = session.xenapi.VIF.get_VM(vifs[i])
            a_vm_name = session.xenapi.VM.get_name_label(vmref)
            log.debug(str(i)+"."+session.xenapi.network.get_name_label(
             session.xenapi.VIF.get_network(
                vifs[i]))+" "+a_vm_name)
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
        if cpus != "default":
            log.info("Setting cpus to " + cpus)
            session.xenapi.VM.set_VCPUs_max(vm, int(cpus))
            session.xenapi.VM.set_VCPUs_at_startup(vm, int(cpus))
        if maxmemory != "default":
            log.info("Setting memory to " + maxmemory)
            session.xenapi.VM.set_memory(vm, maxmemory) # 8GB="8589934592" or 4GB="4294967296"
        session.xenapi.VM.provision(vm)
        log.info("Starting VM")
        session.xenapi.VM.start(vm, False, True)
        log.debug("  VM is booting")

        log.debug("Waiting for the installation to complete")

        # Here we poll because we don't generate events for metrics objects currently
        def read_power_state(a_vm):
            try:
                record = session.xenapi.VM.get_record(a_vm)
                power_state = record["power_state"]
                if power_state == "Running":
                    return power_state
                return None
            except:
                return None

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
                log.debug(os.keys())
                if "0/ip" in os.keys():
                    return os["0/ip"]
                elif "1/ip" in os.keys():
                    return os["1/ip"]
                return None
            except:
                return None

        def read_cpu_memory(a_vm):
            vgm = session.xenapi.VM.get_guest_metrics(a_vm)
            try:
                vm_mem= session.xenapi.VM_guest_metrics.get_memory(vgm)
                return vm_mem
            except:
                return None

        def read_disks(a_vm):
            vgm = session.xenapi.VM.get_guest_metrics(a_vm)
            try:
                vm_disks= session.xenapi.VM_guest_metrics.get_disks(vgm)
                return vm_disks
            except:
                return None

        # Get the OS Name and IPs
        log.info("Getting the OS Name and IP...")
        config = read_config()
        vm_network_timeout_secs = int(config.get("common", "vm.network.timeout.secs"))
        if (vm_network_timeout_secs > 0):
            TIMEOUT_SECS = vm_network_timeout_secs

        log.info("Max wait time in secs for VM OS address is " + str(TIMEOUT_SECS))
        if not "win" in template:
            maxtime = time.time() + TIMEOUT_SECS
            while read_os_name(vm) is None and time.time() < maxtime:
                time.sleep(1)
            vm_os_name = read_os_name(vm)
            log.info("VM OS name: {}".format(vm_os_name))
        else:
            #TBD: Wait for network to refresh on Windows VM
            time.sleep(60)

        log.info("Max wait time in secs for IP address is " + str(TIMEOUT_SECS))
        maxtime = time.time() + TIMEOUT_SECS
        while read_ip_address(vm) is None and time.time() < maxtime:
            time.sleep(1)
        vm_ip_addr = read_ip_address(vm)
        log.info("VM IP: {}".format(vm_ip_addr))

        # Measure time taken for VM provisioning
        prov_end_time = time.time()
        create_duration = round(prov_end_time - prov_start_time)

        # Get other details of VM
        record = session.xenapi.VM.get_record(vm)
        uuid = record["uuid"]
        vcpus = record["VCPUs_max"]
        memory_static_max = record["memory_static_max"]

        #print_all_disks(session, vm)
        disks = get_disks_size(session, vm)
        log.debug(disks)
        disks_info = ','.join([str(elem) for elem in disks])
        log.debug(disks_info)

        # Save as doc in CB
        state = "available"
        username = new_vm_name
        pool = "dynamicpool"
        docValue = {}
        docValue["ipaddr"] = vm_ip_addr
        docValue["origin"] = "s827"
        docValue["os"] = os_name
        docValue["state"] = state
        docValue["poolId"] = pool
        docValue["prevUser"] = ""
        docValue["username"] = username
        docValue["ver"] = "12"
        docValue["memory"] = memory_static_max
        docValue["os_version"] = vm_os_name
        docValue["name"] = new_vm_name
        #docValue["mac_address"] = mac_address
        docValue["created_time"] = prov_end_time
        docValue["create_duration_secs"] = create_duration
        docValue["cpu"] = vcpus
        docValue["disk"] = disks_info
        docKey = uuid

        cbdoc = CBDoc()
        cbdoc.save_dynvm_doc(docKey, docValue)

        vm_max_expiry_minutes = int(config.get("common", "vm.expiry.minutes"))
        if (expiry_minutes>vm_max_expiry_minutes):
            log.info("Max allowed expiry in minutes is " + str(vm_max_expiry_minutes))
            expiry_minutes=vm_max_expiry_minutes

        log.info("Starting the timer for expiry of "+ str(expiry_minutes) + " minutes.")
        t = threading.Timer(interval=expiry_minutes*60, function=call_release_url,
                            args=[new_vm_name, os_name, uuid])
        t.setName(new_vm_name+"__"+uuid)
        t.start()



    except Exception as e:
        error = str(e)
        log.error(error)

    return vm_ip_addr, vm_os_name, error

def call_release_url(vm_name, os_name, uuid):
    import ssl
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
        r = urllib.request.urlopen(
            "http://127.0.0.1:5000/releaseservers/" + vm_name + "?os=" + os_name)
    except Exception as e:
        log.info(e)

def delete_vms(session, vm_prefix_names, number_of_vms=1):
    vm_names = vm_prefix_names.split(",")

    vm_info = {}
    for i in range(len(vm_names)):
        if int(number_of_vms)>1:
            for k in range(int(number_of_vms)):
                delete_vm(session, vm_names[i] + str(k+1))
                vm_info[vm_names[i] + str(k+1)] = "deleted"

        else:
            delete_vm(session, vm_names[i])
            vm_info[vm_names[i]] = "deleted"

    return json.dumps(vm_info, indent=2, sort_keys=True)

def delete_vm(session, vm_name):
    log.info("Deleting VM: "+ vm_name)
    delete_start_time = time.time()
    vm = session.xenapi.VM.get_by_name_label(vm_name)
    log.info("Number of VMs found with name - " + vm_name + " : "+ str(len(vm)))
    for j in range(len(vm)):
        record = session.xenapi.VM.get_record(vm[j])
        power_state = record["power_state"]
        if power_state != 'Halted':
            #session.xenapi.VM.shutdown(vm[j])
            session.xenapi.VM.hard_shutdown(vm[j])

        #print_all_disks(session, vm[j])
        delete_all_disks(session, vm[j])

        #vbds = session.xenapi.VM.get_VBDs(vm[j])
        #log.info(vbds)
        #vdi = session.xenapi.VBD.get_VDI(vbds[0])
        #if vdi:
        #    log.info("Deleting the disk...")
        #    log.info(vdi)
        #
        #    try:
        #        session.xenapi.VDI.destroy(vdi)
        #    except Exception as e:
        #        log.error(e)
        #        pass


        session.xenapi.VM.destroy(vm[j])

        delete_end_time = time.time()
        delete_duration = round(delete_end_time - delete_start_time)

        # delete from CB
        uuid = record["uuid"]
        docKey = uuid
        cbdoc = CBDoc()
        docResult = cbdoc.get_doc(docKey)
        if docResult:
            docValue = docResult.value
            docValue["state"] = 'deleted'
            current_time = time.time()
            docValue["deleted_time"] = current_time
            if docValue["created_time"]:
                docValue["live_duration_secs"] = round(current_time - docValue["created_time"])
            docValue["delete_duration_secs"] = delete_duration
            cbdoc.save_dynvm_doc(docKey, docValue)


def read_vm_ip_address(session, a_vm):
    vgm = session.xenapi.VM.get_guest_metrics(a_vm)
    try:
        os = session.xenapi.VM_guest_metrics.get_networks(vgm)
        if "0/ip" in os.keys():
            return os["0/ip"]
        return None
    except:
        return None

def print_all_disks(session, vm):
    vbds = session.xenapi.VM.get_VBDs(vm)
    index=1
    for vbd in vbds:
        vdi = session.xenapi.VBD.get_VDI(vbd)
        if vdi:
            log.info("Disk..."+ str(index))
            log.info(vdi)
            index = index+1
            try:
                #session.xenapi.VDI.destroy(vdi)
                vdi_record = session.xenapi.VDI.get_record(vdi)
                log.info(vdi_record)
                #virtual_size
            except Exception as e:
                log.error(e)
                pass

def get_disks_size(session, vm):
    vbds = session.xenapi.VM.get_VBDs(vm)
    disks = []
    for vbd in vbds:
        if vbd != 'OpaqueRef:NULL':
            vdi = session.xenapi.VBD.get_VDI(vbd)
            if vdi:
                try:
                    if vdi != 'OpaqueRef:NULL':
                        vdi_record = session.xenapi.VDI.get_record(vdi)
                        disks.append(vdi_record['virtual_size'])
                except Exception as e:
                    log.error(e)
                    pass
    return disks

def delete_all_disks(session, vm):
    vbds = session.xenapi.VM.get_VBDs(vm)
    index=1
    for vbd in vbds:
        vdi = session.xenapi.VBD.get_VDI(vbd)
        if vdi != 'OpaqueRef:NULL':
            log.info("Delete Disk..."+ str(index))
            log.debug(vdi)
            index = index+1
            try:
                vdi_record = session.xenapi.VDI.get_record(vdi)
                log.debug(vdi_record)
                session.xenapi.VDI.destroy(vdi)
            except Exception as e:
                log.error(e)
                pass


class CBDoc:
    def __init__(self):
        config = read_config()
        self.cb_server = config.get("couchbase", "couchbase.server")
        self.cb_bucket = config.get("couchbase", "couchbase.bucket")
        self.cb_username = config.get("couchbase", "couchbase.username")
        self.cb_userpassword = config.get("couchbase", "couchbase.userpassword")
        try:
            self.cb_cluster = Cluster('couchbase://' + self.cb_server)
            self.cb_auth = PasswordAuthenticator(self.cb_username, self.cb_userpassword)
            self.cb_cluster.authenticate(self.cb_auth)
            self.cb = self.cb_cluster.open_bucket(self.cb_bucket)
        except Exception as e:
            log.error('Connection Failed: %s ' % self.cb_server)
            log.error(e)

    def get_doc(self, docKey):
        try:
            return self.cb.get(docKey)
            log.info("%s added/updated successfully" % docKey)
        except Exception as e:
            log.error('Error while getting doc %s !' % docKey)
            log.error(e)

    def save_dynvm_doc(self, docKey, docValue):
        try:
            log.info(docValue)
            self.cb.upsert(docKey, docValue)
            log.info("%s added/updated successfully" % docKey)
        except Exception as e:
            log.error('Document with key: %s saving error' %
                      docKey)
            log.error(e)

def list_given_vm_set_details(session, options):
    vm_names = options.list_vm_names.split(",")
    for i in range(len(vm_names)):
        if int(options.number_of_vms) > 1:
            for k in range(int(options.number_of_vms)):
                list_vm_details(session, vm_names[i] + str(k + 1))
        else:
            list_vm_details(session, vm_names[i])

def parse_arguments():
    log.debug("Parsing arguments")
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default=".dynvmservice.ini", help="Configuration file")
    parser.add_argument("-l", "--log-level", dest="loglevel", default="INFO",
                        help="e.g -l info,warning,error")
    options = parser.parse_args()
    return options

def main():
    options = parse_arguments()
    setLogLevel()
    app.run(host='0.0.0.0', debug=True)

if __name__ == "__main__":
    main()

