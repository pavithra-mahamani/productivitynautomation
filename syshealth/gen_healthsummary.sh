#!/bin/bash
############################################################################
# Description: Get the IPs ssh ping and statistics
#
############################################################################

IPS_OR_FILE="$1"
if [ "$IPS_OR_FILE" = "" ]; then
  echo "Usage $0 ips_or_file"
  echo "Example: $0 ip1,ip2,ip3"
  exit 1
fi

IPS_INI=$IPS_OR_FILE
if [ ! -f $IPS_OR_FILE ]; then
  IPS_INI=ips_list.ini
  echo $IPS_OR_FILE |tr "," "\n" > ${IPS_INI}
fi

echo "*** Summary of VMs ***"
echo "----------------------------------------"
ALL_FINAL_UNIQUE_UNREACHABLE=unreachable_all_platforms.txt
cat /dev/null>${ALL_FINAL_UNIQUE_UNREACHABLE}
OINDEX=1

TOTAL_IPS=`wc -l ${IPS_INI}|xargs|cut -f1 -d' '`
echo "Count: ${TOTAL_IPS}"

echo '*** Final Summary ***' >>${ALL_FINAL_UNIQUE_UNREACHABLE}

FAILEDSTATE_LIST=failedstate_all.txt
cat /dev/null>${FAILEDSTATE_LIST}
UPTIME_THRESHOLD=100
UPTIME_LIST=uptime_more_than_${UPTIME_THRESHOLD}days_all.txt
cat /dev/null>${UPTIME_LIST}
MEMTOTAL_THRESHOLD=100
MEMTOTAL_LIST=memtotal_diff_more_${MEMTOTAL_THRESHOLD}mb_all.txt
cat /dev/null>${MEMTOTAL_LIST}
DISK_THRESHOLD=$((15))
DISK_LIST=disk_size_less_${DISK_THRESHOLD}gb_all.txt
cat /dev/null>${DISK_LIST}
VM_OS_USER="`cat ~/.ansible_vars.ini |grep user |cut -f2 -d'='`"
VM_OS_USER_PWD="`cat ~/.ansible_vars.ini |grep pass |cut -f2 -d'='`"

 TTIMED=0
 TUNREACH=0
 INDEX=1
 GRAND=0
 UINDEX=1
 OUT_ALL_UNREACHABLE=unreachable_all.ini
 cat /dev/null>$OUT_ALL_UNREACHABLE
 OUT_ALL_STATE_UNREACHABLE=unreachable_all_state.txt
 cat /dev/null>$OUT_ALL_STATE_UNREACHABLE


    LOG_FILE=ping_log.txt
    OUT_UNREACHABLE=unreachable.ini
    if [ ! -d ansible_out/ ]; then
      mkdir ansible_out/
    else 
      rm -rf ansible_out/*  
    fi
    echo "Running ansible..."
    if [ -f ~/.ansible_vars.ini ]; then
      VAR_FOUND="`grep 'ansible_user' ${IPS_INI}`"
      if [ "${VAR_FOUND}" = "" ]; then
        cat $IPS_INI >${IPS_INI}_ips2
        cat ~/.ansible_vars.ini >>${IPS_INI}_ips2
        ansible all -i ${IPS_INI}_ips2 -u root -m setup --tree ansible_out/ >${LOG_FILE}
      fi
    else
      ansible all -i ${IPS_INI} -u root -m setup --tree ansible_out/ >${LOG_FILE}
    fi
 
    #generate overview fancy html
    INVENTORY_FILE=inventory_setup_details.html
    ansible-cmdb -t html_fancy -p local_js=1,collapsed=1 ansible_out/ > $INVENTORY_FILE
    #Fix the js
    sed 's/.*<\/head>$/<script type="text\/javascript" charset="utf8" src="ansible_cmdb_static\/js\/jquery-1.10.2.min.js"><\/script><script type="text\/javascript" charset="utf8" src="ansible_cmdb_static\/js\/jquery.dataTables.js"><\/script><\/head>/g' ${INVENTORY_FILE} >${INVENTORY_FILE}_1 
    ANSIBLE_CMDB_STATIC=`egrep static ${INVENTORY_FILE} |egrep static |tail -1 |cut -f4 -d'='|cut -f2 -d':'|cut -f1 -d'"'|sed 's/\/\/\//\//g'|rev|cut -f3- -d'/'|rev`
    if [ ! -d ./ansible_cmdb_static ]; then
       echo cp -R ${ANSIBLE_CMDB_STATIC} ansible_cmdb_static
       cp -R ${ANSIBLE_CMDB_STATIC} ansible_cmdb_static
    fi
    cp -r ${INVENTORY_FILE}_1 ${INVENTORY_FILE}
    if [ -f ${INVENTORY_FILE}_1 ]; then
      rm ${INVENTORY_FILE}_1
    fi
    ansible-cmdb -t csv --columns "ip,os,mem,memfree,cpus,disk_mounts,disk_avail,uptime" ansible_out/ |egrep -v 'No' | tr -d '\r'|cut -f1- -d',' >mem_cpus_uptime.txt

    #echo RequiredPool: $REQ_POOL
    TIMEDOUT="`egrep timed ${LOG_FILE} | cut -f4 -d':' |cut -f5 -d' '|wc -l|xargs`"
    UNREACH="`egrep UNREACHABLE ${LOG_FILE} | cut -f5 -d':' |cut -f5 -d' '|wc -l|xargs`"
    SUCCESS="`egrep SUCCESS ${LOG_FILE}| cut -f5 -d':' |cut -f5 -d' '|wc -l|xargs`"
    TOTAL="`egrep '=>' ${LOG_FILE}| cut -f5 -d':' |cut -f5 -d' '|wc -l|xargs`"
    echo " "
    echo "  Total VMs:$TOTAL, Success:$SUCCESS, Unreachable:$UNREACH "'('Timedout:$TIMEDOUT')'
    TTIMED=`expr $TIMEDOUT + $TTIMED`
    TUNREACH=`expr $UNREACH + $TUNREACH`
    
    if [ ! "${SUCCESS}" = "0" ]; then
     SUCCESS_IPS="`egrep SUCCESS ${LOG_FILE} | cut -f1 -d' '`"
     echo "  Success VMs:"
     I2=1
     for IP in `echo ${SUCCESS_IPS}`
     do
        IPQ=`echo ${IP}: |sed 's/\./\\\./g'`
        IPQ2="`echo ${IPQ}|cut -f1 -d':'`"
        IPINFO="`egrep ${IPQ2} ${IPS_INI}`"
        
        MEM_CPU_UPTIME="`grep -w ${IPQ2} mem_cpus_uptime.txt|cut -f2- -d','`"
        echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME}: SUCCESS"
        FAILED_SUCCESS="`echo $IPINFO | egrep failedInstall`"
        if [ ! "$FAILED_SUCCESS" = "" ]; then
            #echo "Failed state........."
            echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME}: SUCCESS" >>${FAILEDSTATE_LIST}
        fi
        #uptime threshold
        UPTIME=`echo ${MEM_CPU_UPTIME}|rev |cut -f1 -d','|rev|xargs`
        if [ ${UPTIME} -gt ${UPTIME_THRESHOLD} ]; then
          echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME}: ---> More than ${UPTIME_THRESHOLD} days since last booted (${UPTIME} days back)" >>${UPTIME_LIST}
        fi
        # memory threshold
        MEMTOTAL=`echo ${MEM_CPU_UPTIME}|cut -f2 -d',' |xargs|tr -dc 0-9`
        MEMMB=$(((MEMTOTAL/1024)*1024))
        MEMDIFF=$((MEMMB-MEMTOTAL))
        if [ $MEMDIFF -lt 0 ]; then
          MEMMB=$((((MEMTOTAL/1024)+1)*1024))
          MEMDIFF=$((MEMMB-MEMTOTAL))
        fi
        if [ $MEMDIFF -gt $MEMTOTAL_THRESHOLD ]; then
          echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME}: ---> ${MEMDIFF}mb than ${MEMTOTAL_THRESHOLD}mb difference in total of ${MEMMB}mb" >>${MEMTOTAL_LIST}
        fi
        # disk (root) threshold
        DISKMOUNTS=`echo ${MEM_CPU_UPTIME}|cut -f5- -d','|rev|cut -f2- -d','|rev|cut -f2 -d'"'|sed 's/ //g'`
        DISKSIZES=`echo ${MEM_CPU_UPTIME}|cut -f5- -d','|rev|cut -f2- -d','|rev|cut -f4 -d'"'|sed 's/ //g'`
        ROOTMOUNTSIZE=0
        MOUNTINDEX=1
        for M in `echo $DISKMOUNTS|sed 's/,/ /g'`
        do
           if [ "${M}" = "/" ]; then
            ROOTMOUNTSIZE=`echo $DISKSIZES|cut -f${MOUNTINDEX} -d','`
            break
           fi
           MOUNTINDEX=`expr ${MOUNTINDEX} + 1`
        done
        ROOTDISKSIZE=`echo $ROOTMOUNTSIZE |cut -f1 -d'.'`
        ROOTGBSIZE=$((ROOTDISKSIZE/1024))
        if [ $ROOTGBSIZE -lt $DISK_THRESHOLD ]; then
          echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME}: ---> ${ROOTGBSIZE}gb is less than expected min ${DISK_THRESHOLD}gb" >>${DISK_LIST}
       
        fi 
        I2=`expr ${I2} + 1`
     done
    fi
    if [ ! "${UNREACH}" = "0" ]; then
     echo "  Unreachable VMs: "
     UNREACH_IPS="`egrep UNREACHABLE ${LOG_FILE} | cut -f1 -d' '`"
     echo "[${NPOOL}_UNREACHABLE]" >${OUT_UNREACHABLE}
     egrep UNREACHABLE ${LOG_FILE} | cut -f1 -d' '>>${OUT_UNREACHABLE}
     for IP in `echo ${UNREACH_IPS}`
     do
         IPQ=`echo ${IP}: |sed 's/\./\\\./g'`
         IPINFO="`egrep ${IPQ} ${IPS_INI}`"
         IPQ2="`echo ${IP} |sed 's/\./\\\./g'` "
         UNREACH_MSG="`egrep UNREACHABLE ${LOG_FILE} -A 3|egrep ${IPQ2} | egrep msg|cut -f2- -d':'|cut -f1 -d','`"
         if [ "$UNREACH_MSG" = "" ]; then
            UNREACH_MSG="`egrep UNREACHABLE ${LOG_FILE} -A 3| egrep msg|cut -f2- -d':'|cut -f1 -d','`"
         fi
         MEM_CPU_UPTIME="`egrep ${IPQ2} mem_cpus_uptime.txt|cut -f2- -d','`"
         echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME} : ${UNREACH_MSG}"
         echo "$IPINFO : ${UNREACH_MSG}" >>$OUT_ALL_STATE_UNREACHABLE
         I2=`expr ${I2} + 1`
         UINDEX=`expr ${UINDEX} + 1`
     done
    echo " "
    INDEX=`expr $INDEX + 1`
    GRAND=`expr $GRAND + ${I2}`
    if [ -f $OUT_UNREACHABLE ]; then
        cat $OUT_UNREACHABLE >>${OUT_ALL_UNREACHABLE}
        echo "" >>${OUT_ALL_UNREACHABLE}
    fi
  fi
 echo "----------------------------------------"
 FINAL_INI=unreachablelist_ips.ini
 echo "[UNREACHABLE]">${FINAL_INI}
 sort $OUT_ALL_UNREACHABLE|uniq|egrep -v '\['|egrep "\S" >>${FINAL_INI}
 UNIQUE=`cat ${FINAL_INI}|egrep -v '\['|wc -l |xargs`

 echo "*** Final list of unreachable IPs,poolids,state ***"
 OUT_FINAL_UNREACHABLE=unreachable_final_list.txt
 cat /dev/null>$OUT_FINAL_UNREACHABLE
 for IP in `cat ${FINAL_INI}|xargs`
 do
  IPQ=`echo ${IP}: |sed 's/\./\\\./g'`
  IPINFO="`egrep ${IPQ} $OUT_ALL_STATE_UNREACHABLE`"
  echo "$IPINFO" >>$OUT_FINAL_UNREACHABLE
 done

 OUT_FINAL_UNIQUE_UNREACHABLE=unreachable_final_unique_list.txt
 cat $OUT_FINAL_UNREACHABLE|sort|uniq|egrep "\S" > $OUT_FINAL_UNIQUE_UNREACHABLE

 cat $OUT_FINAL_UNIQUE_UNREACHABLE

 echo Unique unreachable IPs: $UNIQUE '(Overall unreachable:'$TUNREACH')' '(Total:'$GRAND')'
 echo Please check ${FINAL_INI} file for exact IPs and ${OUT_FINAL_UNIQUE_UNREACHABLE}.
 echo "*** Final Unreachable IPs - ${UNIQUE} ***" >>${ALL_FINAL_UNIQUE_UNREACHABLE}
 cat $OUT_FINAL_UNIQUE_UNREACHABLE >>${ALL_FINAL_UNIQUE_UNREACHABLE}
 OINDEX=`expr ${OINDEX} + 1`

echo
cat ${ALL_FINAL_UNIQUE_UNREACHABLE}
# failedInstall list
FAILEDSTATE_COUNT=`wc -l ${FAILEDSTATE_LIST} |xargs|cut -f1 -d' '`
echo
echo "  Final failedInstall with SUCCESS : ${FAILEDSTATE_COUNT}"
cat ${FAILEDSTATE_LIST} |cut -f2- -d'.'
echo 
# Run fix install
FAILEDINSTALL_POOLS="`cat ${FAILEDSTATE_LIST}  |cut -f2- -d'.'|cut -f3 -d' '|cut -f1 -d','|sort|uniq|xargs`"
for FAILEDPOOL in `echo ${FAILEDINSTALL_POOLS}`
do
  if [ ! -d testrunner ]; then
    git clone http://github.com/couchbase/testrunner
    chmod a+x testrunner/scripts/fix_failed_install.py
  fi
  echo Running testrunner/scripts/fix_failed_install.py ${FAILEDPOOL}
  python testrunner/scripts/fix_failed_install.py ${FAILEDPOOL} ${VM_OS_USER} ${VM_OS_USER_PWD}  
done
# uptime threshold list
UPTIME_COUNT=`wc -l ${UPTIME_LIST} |xargs|cut -f1 -d' '`
echo
echo "  Total Uptime > ${UPTIME_THRESHOLD} days : ${UPTIME_COUNT}"
cat ${UPTIME_LIST} |cut -f2- -d'.'
echo 
# uptime threshold list
MEMDIFF_COUNT=`wc -l ${MEMTOTAL_LIST} |xargs|cut -f1 -d' '`
echo
echo "  Total RAM diff > ${MEMTOTAL_THRESHOLD}mb : ${MEMDIFF_COUNT}"
cat ${MEMTOTAL_LIST} |cut -f2- -d'.'
echo
# disk threshold list
DISK_COUNT=`wc -l ${DISK_LIST} |xargs|cut -f1 -d' '`
echo
echo "  Disk / mount size less than ${DISK_THRESHOLD}gb : ${DISK_COUNT}"
cat ${DISK_LIST} |cut -f2- -d'.'
echo
# 


echo "Check the overall unreachable summary file at ${ALL_FINAL_UNIQUE_UNREACHABLE}"
echo "  inventory details (cpus,mem, disk) file at ${INVENTORY_FILE}"
date
