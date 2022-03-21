import configparser
import sys

def main(confFile):
    src_config = configparser.ConfigParser()
    src_config.read(confFile)
    options = src_config.options("servers")
    print(options)
    servers = []
    for option in options:
        servers.append(src_config.get(src_config.get("servers", option), 'ip'))
    print(servers)

    with open('hosts_template','r') as firstfile, open('/root/cloud/hosts','w') as secondfile: #/root/cloud/hosts

        # read content from first file
        for line in firstfile:

            # append content to second file
            secondfile.write(line)
            if "couchbase_main" in line:
                secondfile.write(f"{servers[0]} services=data,index,query,fts,eventing")

            if "couchbase_nodes" in line:
                for i in range(1,len(servers)):
                    secondfile.write(f"{servers[i]} services=data,index,query,fts\n")



if __name__ == '__main__':
    confFile = sys.argv[1]
    print(confFile)
    main(confFile)