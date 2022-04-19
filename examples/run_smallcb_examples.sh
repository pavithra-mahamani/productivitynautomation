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

load_or_reload_sample()
{
   SAMPLE="$1"
   EXPECTED_ITEM_COUNT=$2
   echo "Load/reloading ${SAMPLE} ...expected items:${EXPECTED_ITEM_COUNT}"
   IS_LOADED=$(curl -s -u${USERNAME}:${PASSWORD} -d '['"\"${SAMPLE}\""']' "http://${HOST}:8091/sampleBuckets/install")
   if [ "${IS_LOADED}" != "[]" ]; then
      IS_ALREADY="`echo $IS_LOADED | grep 'is already loaded'`"
      if [ "${IS_ALREADY}" != "" ]; then
         echo "${SAMPLE} already exists! " #Deleting and loading again for fresh data..."
         #curl -XDELETE -u${USERNAME}:${PASSWORD} "http://${HOST}:8091/pools/default/buckets/${SAMPLE}"
         #sleep 5
         #IS_LOADED=$(curl -s -u${USERNAME}:${PASSWORD} -d '['"\"${SAMPLE}\""']' "http://${HOST}:8091/sampleBuckets/install")
      fi
   fi
   #sleep 10
   TIME_INDEX=1
   ITEM_COUNT=0
   while [[ ( ${ITEM_COUNT} -lt ${EXPECTED_ITEM_COUNT} ) && ( $TIME_INDEX -lt 120 ) ]];
   do
      echo "Waiting to load...${SAMPLE} items:${ITEM_COUNT}...+3 secs"
      sleep 3
      ITEM_COUNT=$(curl -s -u${USERNAME}:${PASSWORD} "http://${HOST}:8091/pools/default/buckets/travel-sample" | \
         python -c 'import sys, json; print(json.load(sys.stdin)["basicStats"]["itemCount"])')
      ((TIME_INDEX++))
   done

   echo "Loaded the ${SAMPLE} items:${ITEM_COUNT}"
   INDEX_PROGRESS=0
   TIME_INDEX=0
   while [[ (${INDEX_PROGRESS} -lt 100 ) && ( $TIME_INDEX -lt 120 ) ]];
   do
      echo "Waiting to create primary index...${SAMPLE} ${INDEX_PROGRESS}%...+3 secs"
      sleep 3
      ITEM_COUNT=$(curl -s -u${USERNAME}:${PASSWORD} "http://${HOST}:8091/pools/default/buckets/travel-sample" | \
            python -c 'import sys, json; print(json.load(sys.stdin)["basicStats"]["itemCount"])')
      INDEX_PROGRESS=$(curl -s -u${USERNAME}:${PASSWORD} "http://${HOST}:8091/indexStatus" | \
            python -c 'import sys, json; data=json.load(sys.stdin);  \
            primary_index=[index for index in data["indexes"] if index["bucket"]=='\""${SAMPLE}"\"' and index["indexName"]=="def_primary"]; \
            print(primary_index[0]["progress"])')
      ((TIME_INDEX++))
   done
   echo "Loaded the ${SAMPLE} primary index:${INDEX_PROGRESS}"
   #sleep 5
   #curl -s -u${USERNAME}:${PASSWORD} -d 'statement=CREATE PRIMARY INDEX idx_primary ON `'"${SAMPLE}"'`' "http://${HOST}:8093/query/service"
   #sleep 5
   echo "Loaded the ${SAMPLE}."

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
      else
         load_or_reload_sample "travel-sample" 63288 
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
