#!/bin/bash
####################################################
# Description: Dynamic VMs lifecycle helper script
#
####################################################
SERVER_API_URL="http://172.23.104.180:5000"
export $@
CPUS="default"
MEM="default"
RESPONSE_FORMAT="detailed"

if [ "${OS}" == "" ]; then
  OS="windows"
fi
if [ ! "${LABELS}" = "" ]; then
  LABELS_OPTION="&labels=${LABELS}"
fi
if [ "${EXPIRY}" == "" ]; then
  EXPIRY="720"
fi
if [ "${OPERATION}" == "help" ] || [ "$1" == "help" ]; then
   echo "Usage: $0 OPERATION= VM_NAME_OR_PREFIX= OS= COUNT= EXPIRY= LABELS="
   echo "Examples:"
   echo " $0 "
   echo " $0 OPERATION=getservers VM_NAME_OR_PREFIX=windows_template_test OS=windows COUNT=6 EXPIRY=1200 LABELS=outofservice"
   echo " $0 OPERATION=releaseservers VM_NAME_OR_PREFIX=windows_template_test OS=windows COUNT=6 LABELS=outofservice"
   echo " $0 LABELS=outofservice"
elif [ "${OPERATION}" = "getservers" ]; then
   if [ ! "${XHOST_REF}" = "" ]; then
     XHOSTREF_OPTION="&xhostref=${XHOST_REF}"
   fi
   if [ $MEM != "default" ]; then
     MEM=$(( $MEM * 1000000000 ))
   fi
   echo curl -s -o ${VM_NAME_OR_PREFIX}.json "${SERVER_API_URL}/getservers/${VM_NAME_OR_PREFIX}?os=${OS}&count=${COUNT}&format=${RESPONSE_FORMAT}${XHOSTREF_OPTION}&cpus=${CPUS}&mem=${MEM}&expiresin=${EXPIRY}${LABELS_OPTION}"
   curl -s -o ${VM_NAME_OR_PREFIX}.json "${SERVER_API_URL}/getservers/${VM_NAME_OR_PREFIX}?os=${OS}&count=${COUNT}&format=${RESPONSE_FORMAT}${XHOSTREF_OPTION}&cpus=${CPUS}&mem=${MEM}&expiresin=${EXPIRY}${LABELS_OPTION}"
   cat ${VM_NAME_OR_PREFIX}.json
   python -m json.tool < ${VM_NAME_OR_PREFIX}.json >${VM_NAME_OR_PREFIX}_pretty.json
   VM_IP_ADDRESS="`cat ${VM_NAME_OR_PREFIX}_pretty.json |egrep ${VM_NAME_OR_PREFIX}|cut -f2 -d':'|xargs|sed 's/,//g'`"
   
   echo $VM_IP_ADDRESS
   for IP in `echo $VM_IP_ADDRESS`
   do
     if [[ $IP =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        echo Valid IP=$IP received
     else
       echo NOT a valid IP=$IP received
       exit 1
     fi
   done
elif [ "${OPERATION}" = "releaseservers" ]; then
   echo curl -s -o vm.json "${SERVER_API_URL}/releaseservers/${VM_NAME_OR_PREFIX}?os=${OS}&count=${COUNT}${LABELS_OPTION}"
   curl -s -o vm.json "${SERVER_API_URL}/releaseservers/${VM_NAME_OR_PREFIX}?os=${OS}&count=${COUNT}${LABELS_OPTION}"
   cat vm.json
else
   OUT_FILE=all_vms.json
   echo curl -s -o ${OUT_FILE} "${SERVER_API_URL}/showall?${LABELS_OPTION}"
   curl -s -o ${OUT_FILE} "${SERVER_API_URL}/showall?${LABELS_OPTION}"
   cat ${OUT_FILE}
   OPERATION="showall"
   VM_NAME_OR_PREFIX="all"
   COUNT=`grep max ${OUT_FILE} |wc -l|xargs`
fi

echo ""
if [ "${OPERATION}" != "help" ] && [ "$1" != "help" ]; then
  #echo curl -s "${SERVER_API_URL}/getavailablecount/${OS}${LABELS_OPTION}"
  AVAILABLE_COUNT=`curl -s "${SERVER_API_URL}/getavailablecount/${OS}${LABELS_OPTION}"`
  echo "OPERATION=${OPERATION},VM_NAME=${VM_NAME_OR_PREFIX},OS=${OS},COUNT=${COUNT},AVAILABLE=${AVAILABLE_COUNT}"
fi
echo "For the help, run: $0 help"
