#!/bin/bash
######################################################
# Description: Run the smallcb/couchbase.live examples
#
######################################################
EXAMPLE_YAML=$1
VERSION="$2"
HOST="$3"
USERNAME="$4"
PASSWORD="$5"
if [ "${EXAMPLE_YAML}" = "" ]; then
   echo "Usage: $0 example-yaml [version=(local|remote|7.0.0-4602|'') host username password]
      Examples:
         $0 basic-java-kv-get.yaml
         $0 basic-*
         $0 basic-java-*
         $0 basic-nodejs-*
         $0 basic-py-*
         $0 basic-go-*
         $0 basic-dotnet-*
         $0 basic-php-*
         $0 basic-ruby-*
         $0 basic-scala-*
         $0 basic-cc-*
      NOTE: local means embedded CB and remote means preexisting server. 
      Check specific docker image for version at http://build-docker.couchbase.com:8020/?page=1#!taglist/couchbase/server-internal
      "
   exit 1
fi
: ${HOST:="127.0.0.1"}
: ${USERNAME:="Administrator"}
: ${PASSWORD:="small-house-secret"}

print_inputs()
{
   echo "
      EXAMPLES=${EXAMPLE_YAML}
      VERSION=${VERSION}
      HOST=${HOST}
      USERNAME=${USERNAME}
   "
}

# build docker image and start the instance
checkout_build_smallcb_docker()
{
   git clone git@github.com:couchbaselabs/smallcb.git
   cd smallcb
   if [[ ( "${VERSION}" == "" ) || ( "${VERSION}" == "local" ) ]]; then
      make build create instance-start
   elif [ "${VERSION}" != "remote" ]; then
      make BUILD_EXTRAS="--build-arg CB_IMAGE=build-docker.couchbase.com/couchbase/server-internal:${VERSION}" build create instance-start
   else
      make IMAGE_FROM=base
      mkdir $PWD/volume-instances
      DOCKER_VOL=/opt/couchbase/var
      docker run --name=smallcb-0 -v $PWD/volume-instances:${DOCKER_VOL} -d smallcb bash -c 'tail -f /dev/null'
   fi
   cd cmd/play-server/static/examples
}

# Run given examples
run_examples()
{
   INDEX=1
   TEST_RESULTS=test_results.csv
   echo "Example,Status" >${TEST_RESULTS}
   PASSED_COUNT=0
   FAILED_COUNT=0
   for YAML_CODE in `ls ${EXAMPLE_YAML}`
   do
      echo --------------------------------------------
      echo "#${INDEX}. Running ${YAML_CODE}"
      echo --------------------------------------------
      LANG_EXTN="`grep 'lang:' ${YAML_CODE}|cut -f2 -d':'|sed -e 's/^ *//g'`"
      CODE="code.${LANG_EXTN}"
      sed -n -e '/code:/,/infoAfter:/ p' ${YAML_CODE} |sed -e '1d' -e '$d' -e 's/^..//g' -e "s/{{.Host}}/${HOST}/g" -e "s/{{.CBUser}}/${USERNAME}/g" -e "s/{{.CBPswd}}/${PASSWORD}/g" >${CODE}
      DOCKER_VOL=/opt/couchbase/var
      
      if [ "${LANG_EXTN}" == "rb" ]; then 
         LANG_EXTN="ruby"
      elif [ "${LANG_EXTN}" == "scala" ]; then 
         LANG_EXTN="scala-sbt"
      fi
      
      # couchbase docker instance restart
      EXAMPLES_DIR=`pwd`
      if [ "${VERSION}" != "remote" ]; then
         cd ../../../../; make restart
      fi
      cd ${EXAMPLES_DIR}
      #
      docker cp  ${CODE} smallcb-0:${DOCKER_VOL}/${CODE}
      docker exec smallcb-0 bash -c "cd ${DOCKER_VOL};  echo ------ Source ------; cat ${CODE}; echo ------ Output:start ------; /run-${LANG_EXTN}.sh ${DOCKER_VOL}/${CODE}; echo ------ Output:end ------; rm ${CODE}" | tee results.log
      STATUS=$?
      OUTPUT="`cat results.log | sed -n -e '/Output:start/,/Output:end/ p'`"
      ANY_ERROR="`echo $OUTPUT | grep -E 'Error|Failure|Exception'`"
      FILENAME="`echo ${YAML_CODE}|cut -f1 -d'.'`"
      if [[ ( "${STATUS}" != "0" ) || ( "${OUTPUT}" == "" ) || ( "${ANY_ERROR}" != "" ) ]]; then
         echo ${FILENAME},"FAILED" >> ${TEST_RESULTS}
         ((FAILED_COUNT++))
      elif [ "${ANY_ERROR}" == "" ]; then
         echo ${FILENAME},"PASSED" >> ${TEST_RESULTS}
         ((PASSED_COUNT++))
      else 
         echo ${FILENAME},"UNKNOWN" >> ${TEST_RESULTS}
      fi
      rm ${CODE}
      ((INDEX++))
   done

   EXAMPLES_DIR=`pwd`
   cd ../../../../; make instance-stop
   cd ${EXAMPLES_DIR}
   echo " ------- Completed examples ------"

   cat ${TEST_RESULTS}
   TOTAL=`expr $PASSED_COUNT + $FAILED_COUNT`
   echo TOTAL=${TOTAL}, PASSED=${PASSED_COUNT}, FAILED=${FAILED_COUNT}

   if [ ${FAILED_COUNT} -gt 0 ]; then
      echo "Failed examples found!"
      exit 1
   fi
}

all()
{
   print_inputs
   checkout_build_smallcb_docker
   run_examples
}

all

echo "Done."
