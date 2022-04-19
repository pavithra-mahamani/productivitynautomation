import configparser
import sys

def create_hosts_file(confFile, inventory_template, hosts_file):
    src_config = configparser.ConfigParser()
    src_config.read(confFile)
    options = src_config.options("servers")
    print(options)
    servers = []
    for option in options:
        ip = src_config.get(src_config.get("servers", option), 'ip')
        try:
            services = src_config.get(src_config.get("servers", option), 'services')
            services = services.replace("kv", "data")
            services = services.replace("n1ql", "query")
        except configparser.NoOptionError:
            services = "data,index,query,fts"

        servers.append({"ip": ip, "services": services})
    print(servers)

    with open(inventory_template,'r') as firstfile, open(hosts_file,'w') as secondfile: #/root/cloud/hosts

        # read content from first file
        for line in firstfile:

            # append content to second file
            secondfile.write(line)
            if "couchbase_main" in line:
                secondfile.write(f"{servers[0].get('ip')} services={servers[0].get('services')}")

            if "couchbase_nodes" in line:
                for i in range(1,len(servers)):
                    secondfile.write(f"{servers[i].get('ip')} services={servers[i].get('services')}\n")

if __name__ == '__main__':
    confFile = sys.argv[1]
    inventory_template = sys.argv[2]
    hosts_file = sys.argv[3]
    print(confFile)
    create_hosts_file(confFile, inventory_template, hosts_file)