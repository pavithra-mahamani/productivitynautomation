#!/bin/bash 
############################################################################################################################################
# Description: Get total commits count between the dates
#   in couchbase and couchbaselabs, any repository containing: "test" or "automation" or sequoia" or "TAF" or "perf" or "build" or "Jython".
#
############################################################################################################################################

START="$1"
END="$2"
USER_PWD="$3"

if [ "${END}" = "" ]; then
  echo "Usage: $0 START_DATE END_DATE [GIT_USER_PASS]"
  echo "Usage: $0 2020-08-01 2020-08-31"
  exit 1
fi

if [ "${USER_PWD}" = "" ]; then
  if [ ! -z  $GIT_USER_PASS ]; then
    USER_PWD="$GIT_USER_PASS"
  else
    echo  "ERROR: GIT_USER_PASS is not given as argument or environment variable!"
    exit 1 
  fi
fi

PRESENT=`pwd`
OUT=$PRESENT/commits_summary_${START}_${END}.txt
echo "*** Commits from ${START} to ${END} *** ">${OUT}
OUT_SHORT=$PRESENT/commits_short_${START}_${END}.txt
echo "*** Commits list from ${START} to ${END} *** ">${OUT_SHORT}
OUT_DETAILED=$PRESENT/commits_detailed_${START}_${END}.txt
echo "*** Detailed Commits from ${START} to ${END} *** ">${OUT_DETAILED}
OUT_ALL_COMMITS=$PRESENT/commits_all_summary_${START}_${END}.txt
echo "*** All commits from ${START} to ${END} *** ">${OUT_ALL_COMMITS}
OUT_REPOS=$PRESENT/commits_repos_${START}_${END}.txt
echo "*** Committed repositories from ${START} to ${END} *** ">${OUT_REPOS}

get_hist()
{

  ORG="$1"
  echo "--> Organization : ${ORG}"
  curl -Is -u${USER_PWD} "https://api.github.com/search/repositories?q=org%3A${ORG}&per_page=100" |egrep -i 'link:' > ${ORG}_pages.txt
  PAGES="`cat ${ORG}_pages.txt|egrep -i 'link' |cut -f2 -d',' | egrep last |grep -o '\&page=\d.' |cut -f2 -d'='|cut -f1 -d'>'`"
  #echo "Total pages: ${PAGES}"
  for PAGE in `seq ${PAGES}`
  do
   #echo "PAGE: ${PAGE}"
   ODIR=`pwd`
   if [ ! -d $ORG ]; then 
    mkdir $ORG
   fi
   cd $ORG
   curl -s -u${USER_PWD} -H"Accept:application/vnd.github.v3+json" "https://api.github.com/search/repositories?q=org%3A${ORG}&per_page=100&page=${PAGE}" | \
    jq -r '.items[] | select(.name | contains("test"), contains("automation"), contains("sequoia"), contains("TAF"), contains("perf"), 
    contains("build"),contains("Jython"),contains("ycsb"),contains("showfast"),contains("cbmonitor"),contains("greenboard"),contains("jinja"),
    contains("java_sdk_client"), contains("sdkd"),contains("qe"),contains("karajan"),contains("cbdyncluster"),contains("couchbase-java-client"),
    contains("couchbase-jvm-core"),contains("couchbase-jvm-clients"),contains("gocbcore"),contains("gocb"),contains("couchbase-net-client"), contains("libcouchbase")) | .clone_url' >${PRESENT}/${ORG}_urls.txt
    #jq -r '.items[] | .clone_url' >${PRESENT}/${ORG}_urls.txt
   for URL in `cat ${PRESENT}/${ORG}_urls.txt`
   do
     REPONAME="`echo ${URL}|sed 's/.git//g'|rev|cut -f1 -d'/'|rev`"
     echo "${REPONAME}"
     if [ ! -d ${REPONAME} ]; then
      git clone ${URL}
     fi
     CURDIR=`pwd`
     cd ${REPONAME}
     echo "Repo: ${ORG}/${REPONAME}" >>${OUT}
     git shortlog --all -s -n -e -c --after ${START} --before ${END}  >> ${OUT}
     echo "Repo: ${ORG}/${REPONAME}" >>${OUT_SHORT}
     git shortlog --all -n -e -c --after ${START} --before ${END} >> ${OUT_SHORT}
     echo "Repo: ${ORG}/${REPONAME}" >>${OUT_DETAILED}
     git log --graph --pretty='%Cred%h%Creset - %C(green)%cd%Creset %C(bold yellow)%d %s %C(bold blue)<%an,%ae>%Creset<%(trailers)' --date short --after ${START} --before ${END} >>${OUT_DETAILED}
     cd $CURDIR
   done
   cd ${ODIR}
  done
}

noncommitted_users()
{
  COMM_USERS=${PRESENT}/committed_users_list_${START}_${END}.txt
  FINAL_COMM_USERS=${PRESENT}/final_committed_users_list_${START}_${END}.txt
  echo "Final committed users from ${START} to ${END}" >${FINAL_COMM_USERS}
  NONCOMM_USERS=${PRESENT}/non_committed_users_list_${START}_${END}.txt
  echo "Non committed users from ${START} to ${END}" >${NONCOMM_USERS}
  #cat ${OUT_SHORT}|egrep -v 'qa@couchbase.com|noreply@github.com' | egrep '@' |rev |cut -f2- -d' '|rev|sort|uniq >${COMM_USERS}
  cat ${OUT_SHORT}|egrep -v 'qa@couchbase.com|noreply@github.com' | egrep '@' >${COMM_USERS}
  
  EXP_USERS=${PRESENT}/all_expected_user_list.txt
  for U in `cat ${EXP_USERS} |cut -f2 -d'<'|cut -f1 -d'>'`
  do
     CHECK_USER="`echo $U|cut -f1 -d'+'`"
     #echo "egrep -i ${U} ${COMM_USERS}"
     IS_EXIST="`egrep -i ${CHECK_USER} ${COMM_USERS}`"
     if [ "${IS_EXIST}" = "" ]; then
        egrep "${CHECK_USER}" ${EXP_USERS} >> ${NONCOMM_USERS}
     else
        DUP="`egrep -i ${CHECK_USER} ${FINAL_COMM_USERS}`"
        if [ "${DUP}" = "" ]; then
          egrep -i ${CHECK_USER} ${COMM_USERS} >> ${FINAL_COMM_USERS}    
        fi  
     fi
  done
  cat ${NONCOMM_USERS}
  echo "Total commits: `cat ${FINAL_COMM_USERS}|egrep -v Final |egrep '\('|rev|cut -f2 -d')'|cut -f1 -d'('|rev |xargs |sed 's/ /+/g' |bc`"
  

}
all()
{
  get_hist couchbase
  get_hist couchbaselabs
  echo "*** Summary ***"
  #echo "cat ${OUT} | egrep -v 'qa@couchbase.com'| egrep '@' -B 1"
  cat ${OUT} | egrep -v 'qa@couchbase.com'| egrep '@' -B 1 >>${OUT_ALL_COMMITS}
  cat ${OUT_ALL_COMMITS}
  echo "*** Commited repositories ***"
  cat ${OUT} | egrep -v 'qa@couchbase.com'|egrep '@' -B 1 |egrep Repo |cut -f2 -d' '|sort >> ${OUT_REPOS}
  cat ${OUT_REPOS}
  echo "To get short details: cat ${OUT_SHORT} |egrep -v 'qa@couchbase.com|noreply@github.com' |awk '/@/,/^$/'"
  echo "For more details: cat ${OUT_DETAILED}"
  #YEAR="`date '+%Y'`"
  #echo "Total commits: `cat ${OUT_DETAILED}| egrep -v 'qa@couchbase.com|noreply'|egrep ${YEAR}|wc -l`"
  noncommitted_users
}
all
