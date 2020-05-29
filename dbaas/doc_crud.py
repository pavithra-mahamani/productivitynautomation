from couchbase.cluster import Cluster
from couchbase.cluster import PasswordAuthenticator
from couchbase.n1ql import N1QLQuery

import os
import sys
from optparse import OptionParser
import threading

######## Update this to your cluster

def parse_inputs():
    parser = OptionParser()
    parser.add_option("-e", "--endpoint", dest="endpoint",
                      help="Enter CB Endpoint, "
                           "example: cb.6a044530-775e-4b24-b5c0-f82e804a67a6.dp.cloud.couchbase.com")
    parser.add_option("-u", "--username", dest="username", help="Enter CB username")
    parser.add_option("-p", "--password", dest="password", help="Enter CB password")
    parser.add_option("-b", "--bucket", dest="bucket", help="Enter CB bucket")
    parser.add_option("-f", "--propsfile", dest="propsfile", help="Enter cluster properties input file")
    parser.add_option("-c", "--count", dest="doc_count", help="Enter number of docs")

    options, args = parser.parse_args()
    return options, args

def get_props(options):
    props = {}
    if options.endpoint:
        props["endpoint"] = options.endpoint
    if options.username:
        props["username"] = options.username
    if options.password:
        props["password"] = options.password
    if options.bucket:
        props["bucket"] = options.bucket

    if options.propsfile:
        propsfile = options.propsfile
        with open(propsfile,"r") as f:
            for line in f:
                line = line.rstrip()
                if line.startswith('#'):
                    continue
                if not "=" in line:
                    continue
                k, v = line.split('=',1)
                props[k.strip()] = v.strip()

        f.close()
    print(props)
    return props


#endpoint = 'cb.6a044530-775e-4b24-b5c0-f82e804a67a6.dp.cloud.couchbase.com'
#username = "muntajagadesh"
#password = "xxx!"
#bucketName = 'couchbasecloudbucket'
options,args = parse_inputs()
props = get_props(options)
try:
    endpoint = props["endpoint"]
    username = props["username"]
    password = props["password"]
    bucketName = props["bucket"]
except:
    #if not endpoint or not username or not password or not bucketName:
    print("Warning: Input is not proper. Please supply the endpoint, username, password, "
          "bucket details in a properties file or as options. Exiting!")
    sys.exit(1)
#### User Input ends here.
# Data
data_user = os.getlogin()
doc_count = 100
if options.doc_count:
    doc_count = int(options.doc_count)

cluster = Cluster('couchbases://' + endpoint + '?ssl=no_verify')  # Update the cluster endpoint
authenticator = PasswordAuthenticator(username, password) 
cluster.authenticate(authenticator)
cb = cluster.open_bucket(bucketName)
print('Bucket connected')

def doc_insert_thread(num=1):
    insert_threads = []
    for i in range(num):
        t = threading.Thread(target=insert_doc, args=(i))
        insert_threads.append(t)
        t.start()

    for thread in insert_threads:
        thread.join()

def insert_doc(x=0):
    print("Creating record " + str(x))
    try:
      cb.insert('u:jagadesh_munta'+str(x), {'name': 'Jagadesh_' + str(x), 'email': 'jagadesh.munta@couchbase.com', 'interests': ['Explore', 'Reading', 'Sharing']})
    except Exception as e:
      print(e)
      pass

doc_insert_thread(5)
# Get
print("Getting the records...")
for x in range (doc_count):
    print("Getting record " + str(x))
    key=('u:jagadesh_munta'+str(x))
    print(cb.get(key).value)

# Update
print("Update the records...")
for x in range (doc_count):
    print("Updating record " + str(x))
    cb.upsert('u:jagadesh_munta'+str(x), {'name': 'Jagadesh_' + str(x), 'email': 'jagadesh.munta@couchbase.com', 'interests': ['Explore...', 'Reading...', 'Sharing...']})

# Get
print("Getting the records...")
for x in range (doc_count):
    print("Getting record " + str(x))
    key=('u:jagadesh_munta'+str(x))
    print(cb.get(key).value)

# Delete
print("Deleting the records...")
for x in range (doc_count):
    print("Deleting record " + str(x))
    key=('u:jagadesh_munta'+str(x))
    cb.remove(key)

