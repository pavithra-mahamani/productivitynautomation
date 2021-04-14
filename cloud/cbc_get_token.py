import sys
import os
import datetime
import base64
import hmac
import hashlib
import json


if len(sys.argv) < 3:
  print("Couchbase Cloud API handy tool\nUsage:\n export cbc_access_key=<your-access-key>\n export cbc_secret_key=<your-secret-key>")
  print("\n {} API_METHOD API_PATH [ARGS]".format(sys.argv[0]))
  print("\nExamples:\n {} GET /v2/clouds".format(sys.argv[0]))
  print("\n {} GET /v2/projects".format(sys.argv[0]))
  print("\n {} GET /v2/clusters".format(sys.argv[0]))
  print("\n {} POST /v2/projects project_name".format(sys.argv[0]))
  print("\n {} POST /v2/clusters cloud_uuid project_uuid cluster_name".format(sys.argv[0]))
  print("\nReference:\n https://docs.couchbase.com/cloud/public-api-guide/using-cloud-public-api.html \n")
  sample="""
  python3 cbc_get_token.py GET /v2/clouds
  Headers to set: 
  {'Authorization': 'Bearer xxxx:yyyy=', 'Couchbase-Timestamp': '1618275211103'}
  
  Command:
   curl -H 'Authorization:Bearer xxxx:yyyy=' -H 'Couchbase-Timestamp:1618275211103' -X GET 'https://cloudapi.cloud.couchbase.com//v2/clouds'
  
  
  {"cursor":{"pages":{"page":1,"last":1,"perPage":10,"totalItems":1},"hrefs":{"first":"http://cloudapi.cloud.couchbase.com/public/v2/clouds?page=1\u0026perPage=10","last":"http://cloudapi.cloud.couchbase.com/public/v2/clouds?page=1\u0026perPage=10"}},"data":[{"id":"6e85f18f-ef32-4ea9-8a5c-f1e705313f72","name":"QECloudTest","provider":"aws","region":"us-east-1","status":"ready","virtualNetworkCIDR":"10.21.0.0/16","virtualNetworkID":"vpc-089457bb2f3cac2d7"}]}
  """
  print("Sample I/O:\n {}".format(sample))
  exit(1)

cbc_api_method = sys.argv[1]
cbc_api_endpoint = sys.argv[2]
cbc_access_key = os.environ.get('cbc_access_key')
cbc_secret_key = os.environ.get('cbc_secret_key')

# Epoch time in milliseconds
cbc_api_now =  int(datetime.datetime.now().timestamp() * 1000)

# Form the message string for the Hmac hash
cbc_api_message= cbc_api_method + '\n' + cbc_api_endpoint + '\n' + str(cbc_api_now)

# Calculate the hmac hash value with secret key and message
cbc_api_signature = base64.b64encode(hmac.new(bytes(cbc_secret_key, 'utf-8'), bytes(cbc_api_message,'utf-8'), digestmod=hashlib.sha256).digest())

# Values for the header
cbc_api_request_headers = {
   'Authorization' : 'Bearer ' + cbc_access_key + ':' + cbc_api_signature.decode() ,
   'Couchbase-Timestamp' : str(cbc_api_now)
}
print("Headers to set: \n{}".format(cbc_api_request_headers))

if cbc_api_method == "POST": 
   if "projects" in cbc_api_endpoint:
      body_data = {"name": sys.argv[3]}
   elif "clusters" in cbc_api_endpoint:
      body_data = {
	"cloudId": sys.argv[3],
  	"projectId": sys.argv[4],
  	"name": sys.argv[5],
  	"servers": [
    	{
      		"services": [
        	"data",
        	"query",
        	"index",
        	"search"
      		],
      		"size": 3,
      		"aws": {
        		"ebsSizeGib": 1227,
        		"instanceSize": "r5.xlarge"
      		}
    	}
  	],
  	"supportPackage": {
    		"timezone": "PT",
    		"type": "developerPro"
  	}
      }
   post_data = ' -H "Content-Type:application/json" --data-raw \''+json.dumps(body_data)+'\''
else:
   post_data=""

cmd='curl -H \'Authorization:{}\' -H \'Couchbase-Timestamp:{}\' -X {} {} \'https://cloudapi.cloud.couchbase.com/{}\''.format(cbc_api_request_headers['Authorization'], cbc_api_request_headers['Couchbase-Timestamp'], cbc_api_method, post_data, cbc_api_endpoint)
print('\nCommand:\n {}\n'.format(cmd))
os.system(cmd)
print('\n')
