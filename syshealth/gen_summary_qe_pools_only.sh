#!/bin/bash
############################################################################
# Description: Get the IPs ssh ping and statistics
#
############################################################################

LOS="$1"
USED_POOLS="$2"

if [ "$USED_POOLS" = "" ]; then
  echo "Usage $0 os used_pools_file"
  echo "Example: $0 linux_or_centos_or_comma_listed_platforms file"
  echo "Example: $0 linux file"
  echo "Example: $0 centos,suse12 file"
  exit 1
fi

VMS_COUNT_FILE=vms_os_count.txt
echo "*** Summary of QE ServerPool VMs ***"
cat ${VMS_COUNT_FILE}
echo "------------------------------------"

ALL_FINAL_UNIQUE_UNREACHABLE=unreachable_all_platforms.txt
cat /dev/null>${ALL_FINAL_UNIQUE_UNREACHABLE}
OINDEX=1
if [ "$LOS" = "linux" ]; then
  LOS="`cat ${VMS_COUNT_FILE} |cut -f1 -d":"|egrep -v win |xargs|sed 's/ /,/g'`"
fi

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

echo "NOTE: Selected list of QE server pool platforms: ${LOS}"
for OS in `echo $LOS|sed 's/,/ /g'`
do
 OS_COUNT="`grep -w ${OS} vms_os_count.txt`"
 echo
 echo "*** Platform#${OINDEX}. Total VMs on ${OS_COUNT}"
 echo "----------------------------------------"
 echo "Server pools list on ${OS}"
 echo "----------------------------------------"
 cat vmpools_${OS}_counts.txt
 echo "----------------------------------------"
 TTIMED=0
 TUNREACH=0
 INDEX=1
 GRAND=0
 UINDEX=1
 OUT_ALL_UNREACHABLE=unreachable_all_${OS}.ini
 cat /dev/null>$OUT_ALL_UNREACHABLE
 OUT_ALL_STATE_UNREACHABLE=unreachable_all_state_${OS}.txt
 cat /dev/null>$OUT_ALL_STATE_UNREACHABLE


 for line in `cat ${USED_POOLS}`
 do
  POOL="$line"
  REQ_POOL="`grep -iw $POOL vmpools_${OS}_counts.txt`"
  if [ ! "$REQ_POOL" = "" ]; then
    echo "$INDEX. Server Pool: $POOL"
    NPOOL="`echo $line|sed -e 's/ //' -e 's/-//g'`"
    LOG_FILE=ping_log_${OS}_${NPOOL}.txt
    OUT_UNREACHABLE=unreachable_${NPOOL}.ini
    #echo ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m ping
    if [ ! -d ansible_out/ ]; then
      mkdir ansible_out/
    fi
    if [ -f ~/.ansible_vars.ini ]; then
      VAR_FOUND="`grep 'ansible_user' vmpools_${OS}_ips.ini`"
      if [ "${VAR_FOUND}" = "" ]; then
        cat vmpools_${OS}_ips.ini >vmpools_${OS}_ips2.ini
        cat ~/.ansible_vars.ini >>vmpools_${OS}_ips2.ini
        #ansible ${NPOOL} -i vmpools_${OS}_ips2.ini -u root -m ping >${LOG_FILE}
        echo ansible ${NPOOL} -i vmpools_${OS}_ips2.ini -u root -m setup --timeout 20 --tree ansible_out/
        ansible ${NPOOL} -i vmpools_${OS}_ips2.ini -u root -m setup --timeout 20 --tree ansible_out/ >${LOG_FILE}
      fi
    else
      #ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m ping >${LOG_FILE}
      echo ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m setup --timeout 20 --tree ansible_out/
      ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m setup --timeout 20 --tree ansible_out/ >${LOG_FILE}
    fi
 
    #generate overview fancy html
    echo generate overview fancy html
    INVENTORY_FILE=inventory_for_selectedpools.html
    echo ansible-cmdb -t html_fancy -p local_js=1,collapsed=1 ansible_out/
    ansible-cmdb -t html_fancy -p local_js=1,collapsed=1 ansible_out/ > $INVENTORY_FILE
    #Fix the js
    echo Fix the js
    sed 's/.*<\/head>$/<script type="text\/javascript" charset="utf8" src=".\/ansible_cmdb_static\/js\/jquery-1.10.2.min.js"><\/script><script type="text\/javascript" charset="utf8" src=".\/ansible_cmdb_static\/js\/jquery.dataTables.js"><\/script><\/head>/g' ${INVENTORY_FILE} >${INVENTORY_FILE}_1 
    ANSIBLE_CMDB_STATIC=`egrep static ${INVENTORY_FILE} |egrep static |tail -1 |cut -f4 -d'='|cut -f2 -d':'|cut -f1 -d'"'|sed 's/\/\/\//\//g'|rev|cut -f3- -d'/'|rev`
    if [ ! -d ./ansible_cmdb_static ]; then
       echo cp -R ${ANSIBLE_CMDB_STATIC} ansible_cmdb_static
       cp -R ${ANSIBLE_CMDB_STATIC} ansible_cmdb_static
    fi
    cp -r ${INVENTORY_FILE}_1 ${INVENTORY_FILE}
    if [ -f ${INVENTORY_FILE}_1 ]; then
      rm ${INVENTORY_FILE}_1
    fi
    if [ ! -d qeinfra ]; then
      mkdir qeinfra
    fi
    cp ${INVENTORY_FILE} qeinfra
    cp ${INVENTORY_FILE} qeinfra/index.html
    cp -R ansible_cmdb_static qeinfra
    aws s3 cp qeinfra s3://cb-logs-qe/qeinfra --recursive
    ansible-cmdb -t csv --columns "ip,os,mem,memfree,cpus,disk_mounts,disk_avail,uptime" ansible_out/ |egrep -v 'No' | tr -d '\r'|cut -f1- -d',' >${OS}_${NPOOL}_mem_cpus_uptime.txt

    #echo RequiredPool: $REQ_POOL
    TIMEDOUT="`egrep timed ${LOG_FILE} | cut -f4 -d':' |cut -f5 -d' '|wc -l|xargs`"
    UNREACH="`egrep UNREACHABLE ${LOG_FILE} | cut -f5 -d':' |cut -f5 -d' '|wc -l|xargs`"
    SUCCESS="`egrep SUCCESS ${LOG_FILE}| cut -f5 -d':' |cut -f5 -d' '|wc -l|xargs`"
    TOTAL="`egrep '=>' ${LOG_FILE}| cut -f5 -d':' |cut -f5 -d' '|wc -l|xargs`"
    echo " "
    echo "  Total VMs:$TOTAL, Success:$SUCCESS, Unreachable:$UNREACH "'('Timedout:$TIMEDOUT')'
    TTIMED=`expr $TIMEDOUT + $TTIMED`
    TUNREACH=`expr $UNREACH + $TUNREACH`
    #if [ ! "${TIMEDOUT}" = "0" ]; then
    # echo "  Timedout VMs: "
    # TIMEDOUT_IPS="`egrep timed ${LOG_FILE} | cut -f4 -d':' |cut -f5 -d' '`"
    # echo "[${NPOOL}_TIMEDOUT]" >${OUT_UNREACHABLE}
    # egrep timed ${LOG_FILE} | cut -f4 -d':' |cut -f5 -d' ' >>${OUT_UNREACHABLE}
    # for IP in `echo ${TIMEDOUT_IPS}`
    # do
    #     egrep $IP vms_list_${OS}_ips.ini
    # done
    #fi
    if [ ! "${SUCCESS}" = "0" ]; then
     SUCCESS_IPS="`egrep SUCCESS ${LOG_FILE} | cut -f1 -d' '`"
     echo "  Success VMs:"
     I2=1
     for IP in `echo ${SUCCESS_IPS}`
     do
        IPQ=`echo ${IP}: |sed 's/\./\\\./g'`
        IPINFO="`egrep ${IPQ} vms_list_${OS}_ips.ini`"
        IPQ2="`echo ${IPQ}|cut -f1 -d':'`"
        #echo egrep ${IPQ2} ${OS}_${NPOOL}_mem_cpus_uptime.txt
        MEM_CPU_UPTIME="`grep -w ${IPQ2} ${OS}_${NPOOL}_mem_cpus_uptime.txt|cut -f2- -d','`"
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
        # fix total expected memory to 4GB than automatic calculation
        #MEMMB=$(((MEMTOTAL/1024)*1024))
        MEMMB=4096
        MEMDIFF=$((MEMTOTAL-MEMMB))
        #if [ $MEMDIFF -lt 0 ]; then
        #  MEMMB=$((((MEMTOTAL/1024)+1)*1024))
        #  MEMDIFF=$((MEMMB-MEMTOTAL))
        #fi
        if [ $MEMDIFF -lt 0 ]; then
          OMEMDIFF=${MEMDIFF}
          MEMDIFF=$((0-${MEMDIFF}))
        fi
        if [ $MEMDIFF -gt $MEMTOTAL_THRESHOLD ]; then
          echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME}: ---> ${OMEMDIFF}mb than ${MEMTOTAL_THRESHOLD}mb difference in total of ${MEMMB}mb" >>${MEMTOTAL_LIST}
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
         IPINFO="`egrep ${IPQ} vms_list_${OS}_ips.ini`"
         IPQ2="`echo ${IP} |sed 's/\./\\\./g'` "
         UNREACH_MSG="`egrep UNREACHABLE ${LOG_FILE} -A 3|egrep ${IPQ2} | egrep msg|cut -f2- -d':'|cut -f1 -d','`"
         if [ "$UNREACH_MSG" = "" ]; then
            UNREACH_MSG="`egrep UNREACHABLE ${LOG_FILE} -A 3| egrep msg|cut -f2- -d':'|cut -f1 -d','`"
         fi
         MEM_CPU_UPTIME="`egrep ${IPQ2} ${OS}_${NPOOL}_mem_cpus_uptime.txt|cut -f2- -d','`"
         echo "   ${I2}. $IPINFO, ${MEM_CPU_UPTIME} : ${UNREACH_MSG}"
         echo "$IPINFO : ${UNREACH_MSG}" >>$OUT_ALL_STATE_UNREACHABLE
         I2=`expr ${I2} + 1`
         UINDEX=`expr ${UINDEX} + 1`
     done
    fi
    echo " "
    INDEX=`expr $INDEX + 1`
    GRAND=`expr $GRAND + ${I2}`
    if [ -f $OUT_UNREACHABLE ]; then
        cat $OUT_UNREACHABLE >>${OUT_ALL_UNREACHABLE}
        echo "" >>${OUT_ALL_UNREACHABLE}
    fi
  fi
 done

 echo "----------------------------------------"
 FINAL_INI=unreachablelist_ips_${OS}.ini
 echo "[UNREACHABLE]">${FINAL_INI}
 sort $OUT_ALL_UNREACHABLE|uniq|egrep -v '\['|egrep "\S" >>${FINAL_INI}
 UNIQUE=`cat ${FINAL_INI}|egrep -v '\['|wc -l |xargs`

 echo "*** Final list of unreachable IPs,poolids,state ***"
 OUT_FINAL_UNREACHABLE=unreachable_final_list_${OS}.txt
 cat /dev/null>$OUT_FINAL_UNREACHABLE
 for IP in `cat ${FINAL_INI}|xargs`
 do
  IPQ=`echo ${IP}: |sed 's/\./\\\./g'`
  IPINFO="`egrep ${IPQ} $OUT_ALL_STATE_UNREACHABLE`"
  echo "$IPINFO" >>$OUT_FINAL_UNREACHABLE
 done

 OUT_FINAL_UNIQUE_UNREACHABLE=unreachable_final_unique_list_${OS}.txt
 cat $OUT_FINAL_UNREACHABLE|sort|uniq|egrep "\S" > $OUT_FINAL_UNIQUE_UNREACHABLE

 cat $OUT_FINAL_UNIQUE_UNREACHABLE

 echo Unique unreachable IPs: $UNIQUE '(Overall unreachable:'$TUNREACH')' '(Total:'$GRAND')'
 echo Please check ${FINAL_INI} file for exact IPs and $OUT_FINAL_UNIQUE_UNREACHABLE along with state.
 echo "*** Final Unreachable IPs on OS: ${OS} - ${UNIQUE} ***" >>${ALL_FINAL_UNIQUE_UNREACHABLE}
 cat $OUT_FINAL_UNIQUE_UNREACHABLE >>${ALL_FINAL_UNIQUE_UNREACHABLE}
 OINDEX=`expr ${OINDEX} + 1`
done
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
echo "  inventory details (cpus,mem, disk) file at http://cb-logs-qe.s3.us-west-2.amazonaws.com/qeinfra/${INVENTORY_FILE}"
date
