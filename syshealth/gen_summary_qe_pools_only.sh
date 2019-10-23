#!/bin/bash
############################################################################
# Description: Get the IPs ssh ping and statistics
#
############################################################################

OS="$1"
USED_POOLS="$2"

if [ "$USED_POOLS" = "" ]; then
  echo "Usage $0 os used_pools_file"
  echo "Example: $0 centos file"
  exit 1
fi

OS_COUNT="`grep ${OS} vms_os_count.txt`"
echo "Total VMs on ${OS_COUNT}"
echo "----------------------------------------"
echo "Server pools list on ${OS}"
echo "----------------------------------------"
cat vmpools_${OS}_counts.txt
echo "----------------------------------------"
TTIMED=0
TUNREACH=0
INDEX=1
GRAND=0
OUT_ALL_UNREACHABLE=unreachable_all_${NPOOL}.ini
cat /dev/null>$OUT_ALL_UNREACHABLE
for line in `cat vmpools_${OS}_counts.txt|cut -f1 -d':'`
do
  POOL="$line"
  REQ_POOL="`grep -iw $POOL ${USED_POOLS}`"
  if [ ! "$REQ_POOL" = "" ]; then
    echo "$INDEX. Server Pool: $POOL"
    NPOOL="`echo $line|sed -e 's/ //' -e 's/-//g'`"
    LOG_FILE=ping_log_${OS}_${NPOOL}.txt
    OUT_UNREACHABLE=unreachable_${NPOOL}.ini
    #echo ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m ping
    if [ -f ~/.ansible_vars.ini ]; then
      VAR_FOUND="`grep 'ansible_user' vmpools_${OS}_ips.ini`"
      if [ "${VAR_FOUND}" = "" ]; then
        cat vmpools_${OS}_ips.ini >vmpools_${OS}_ips2.ini
        cat ~/.ansible_vars.ini >>vmpools_${OS}_ips2.ini
        ansible ${NPOOL} -i vmpools_${OS}_ips2.ini -u root -m ping >${LOG_FILE}
      fi
    else
      ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m ping >${LOG_FILE}
    fi
 
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
        echo "   ${I2}. $IPINFO : SUCCESS"
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
         echo "   ${I2}. $IPINFO : ${UNREACH_MSG}"
         I2=`expr ${I2} + 1`
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
FINAL_INI=unreachablelist_ips.ini
echo "[UNREACHABLE]">${FINAL_INI}
sort $OUT_ALL_UNREACHABLE|uniq >>${FINAL_INI}
UNIQUE=`cat ${FINAL_INI}|egrep -v '\[' |wc -l |xargs`
echo Unique unreachable IPs: $UNIQUE '(Overall unreachable:'$TUNREACH')' '(Total:'$GRAND')'

echo Please check ${FINAL_INI} file for exact IPs.
date
