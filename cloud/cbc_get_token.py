import sys
import os
import datetime
import base64
import hmac
import hashlib


if len(sys.argv) < 3:
  print("Usage:\n export cbc_access_key=<your-access-key>\n export cbc_secret_key=<your-secret-key>")
  print("\n {} API_METHOD API_PATH".format(sys.argv[0]))
  print("\nExample:\n {} GET /v2/clouds".format(sys.argv[0]))
  print("\nReference:\n https://docs.couchbase.com/cloud/public-api-guide/using-cloud-public-api.html \n")
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
cmd='curl -H \'Authorization:{}\' -H \'Couchbase-Timestamp:{}\' -X {} \'https://cloudapi.cloud.couchbase.com/{}\''.format(cbc_api_request_headers['Authorization'], cbc_api_request_headers['Couchbase-Timestamp'], cbc_api_method, cbc_api_endpoint)
print('\nCommand:\n {}\n'.format(cmd))
os.system(cmd)
print('\n')
