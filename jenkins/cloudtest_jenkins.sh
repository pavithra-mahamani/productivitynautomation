#!/bin/bash
WORKSPACE=.
ACTION="$1"
CB_HOST="$2"
CB_USER="$3"
CB_USER_PWD="$4"
INCLUDE_SERVICES="$5"
MGMT_PORT="$6"
IS_ADMIN="$7"
EXCLUDE_SERVICES="$8"

if [ "$IS_ADMIN" = "" ]; then
  echo "Usage:$0 ACTION CB_HOST CB_USER CB_USER_PWD INCLUDE_SERVICES MGMT_PORT IS_ADMIN EXCLUDE_SERVICES"
  exit 1
fi

echo Desc:${CB_HOST}
git clone http://github.com/couchbaselabs/productivitynautomation.git
AUTO_DIR=$WORKSPACE/productivitynautomation
chmod a+x $AUTO_DIR/cloudtest.sh

if [ ! "${GERRIT_PICK}" = "" ]; then
   export GERRIT_PICK="${GERRIT_PICK}"
fi

prereq()
{
  # pre-req 
  echo $AUTO_DIR/cloudtest.sh prereq ${CB_HOST} ${CB_USER} ${CB_USER_PWD} ${INCLUDE_SERVICES} ${MGMT_PORT}
  $AUTO_DIR/cloudtest.sh prereq ${CB_HOST} ${CB_USER} ${CB_USER_PWD} ${INCLUDE_SERVICES} ${MGMT_PORT}
}

run()
{
  # run tests
  if [ ! "${IS_ADMIN}" = "true" ]; then
  	EXCLUDE_FLAG="-e req_admin=True|req_role=views_admin"
    if [ -z ${ADDL_PARAMS} ]; then
      ADDL_PARAMS="is_admin=False"
      export ADDL_PARAMS=${ADDL_PARAMS}
    else
      ADDL_PARAMS="${ADDL_PARAMS},is_admin=False" 
      export ADDL_PARAMS=${ADDL_PARAMS} 
    fi  
  fi
  
  if [ ! "${EXCLUDE_SERVICES}" = "" ]; then
    for SERVICE in `echo ${EXCLUDE_SERVICES}|sed 's/,/ /g'`
    do
       if [ "${SERVICES_REGEX}" = "" ]; then
       	  SERVICES_REGEX=".*${SERVICE}"
       else
          SERVICES_REGEX="${SERVICES_REGEX}|.*${SERVICE}"
       fi
    done
    if [ "${EXCLUDE_FLAG}" = "" ]; then
       EXCLUDE_FLAG="-e req_services=(${SERVICES_REGEX})"
    else
       EXCLUDE_FLAG="${EXCLUDE_FLAG}|req_services=(${SERVICES_REGEX})"
    fi
    
  fi
  
  if [ "${CB_HOST_PRIVATE_IP}" = "" ]; then
    CB_HOST_MAP="${CB_HOST}"
  else
    CB_HOST_MAP="${CB_HOST_PRIVATE_IP}:${CB_HOST}"
  fi
  
  echo $AUTO_DIR/cloudtest.sh run ${CB_HOST_MAP} ${CB_USER} ${CB_USER_PWD} ${INCLUDE_SERVICES} ${MGMT_PORT} ${EXCLUDE_FLAG}
  $AUTO_DIR/cloudtest.sh run ${CB_HOST_MAP} ${CB_USER} ${CB_USER_PWD} ${INCLUDE_SERVICES} ${MGMT_PORT} ${EXCLUDE_FLAG} ${ADDL_PARAMS}

}

reset()
{
  # reset
  echo $AUTO_DIR/cloudtest.sh reset default
  $AUTO_DIR/cloudtest.sh reset default
}

all()
{
  run
  reset
}

all()
{
  prereq
  run
  reset
}

if [ "${ACTION}" = "all" ]; then
    all
elif [ "${ACTION}" = "run" ]; then
    run
elif [ "${ACTION}" = "prereq" ]; then
    prereq
elif [ "${ACTION}" = "reset" ]; then
    reset  
elif [ "${ACTION}" = "runandreset" ]; then
    runandreset
fi


