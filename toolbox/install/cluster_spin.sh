#!/usr/bin/env bash
set -x
### cluster: manage a containerised N-node couchbase cluster with docker-compose
###
### Usage: ./cluster [action] [options]
###
### Actions:
###    up    provision new cluster
###    down  destroy existing cluster
###
### Options:
###    -P --prefix        Cluster prefix/namespace (default: sandbox)
###    -u --user          Administrator username (default: Administrator)
###    -p --pass          Administrator password (default: password)
###    -i --image         Container image (default: couchbase:latest)
###    -v --version       Version and build number to install e.g. 7.0.0-3000 (not for use with --image)
###    -b --base-image    Base image to use when building with --version (default: ubuntu:18.04)
###    -e --edition       Edition: community/enterprise (default: enterprise, has no effect unless used with --version)
###    -s --services      Couchbase services to configure (default: data,index,query,eventing,fts)
###    -C --cpu-limit     Number of cores per container (default: unspecified)
###    -c --cidr          CIDR block (default: 172.18.0.0/16)
###    -M --mem-limit  Container memory limit
###    -n --nodes         List of nodes (default: master:172.18.0.2,node1:172.18.0.3,node2:172.18.0.4,node3:172.18.0.5)
###    -r --restart       Restart policy (no, always, on-failure, default: unless-stopped)
###    -w --workdir       Directory to save content (Dockerfile/docker-compose.yml and packages default: /tmp/cluster-setup-files)
###    -d --debug         Debug output

set -e

help() {
    awk 'sub("^### ?","")' "$0"
}

debug() {
    echo "# DEBUG: $@"
}

execute() {
    if [ "${debug}" = "true" ]; then debug $@; fi
    $@
}

[ "${1}" != "down" -a "${1}" != "up" ] && help && echo && echo "Incorrect action '${1}', only up and down are valid choices" && exit
action=${1}; shift

verbose="&>/dev/null"

# Unpack arguments
while [ $# -gt 0 ]; do
  case "$1" in
    --debug|-d)
      debug="true"
      ;;
    --base-image|-b)
      base_image="${2}"; shift
      ;;
    --image|-i)
      image="${2}"; shift
      ;;
    --version|-v)
      version=$(echo ${2} | cut -f1 -d"-")
      build=$(echo ${2} | cut -f2 -d"-")
      shift
      ;;
    --workdir|-w)
      workdir="${2}"; shift
      ;;
    --edition|-e)
      edition="${2}"; shift
      ;;
    --user|-u)
      username="${2}"; shift
      ;;
    --pass|-p)
      password="${2}"; shift
      ;;
    --prefix|-P)
      cluster_prefix="${2}"; shift
      ;;
    --services|-s)
      services="${2}"; shift
      ;;
    --cpu-limit|-C)
      cpu_limit="'${2}'"; shift
      ;;
    --mem-limit|-M)
      mem_limit="'${2}'"; shift
      ;;
    --cidr|-c)
      cidr_block="${2}"; shift
      ;;
    --nodes|-n)
      nodes=($(echo ${2//,/ })); shift
      ;;
    --restart|-r)
      restart_policy="${2}"; shift
      ;;
    *)
      help
      echo
      printf "****************************\n"
      printf "* Error: Invalid argument: *\n"
      printf "****************************\n"
      echo "${1} is not a recognized argument"
      exit 1
      ;;
  esac
  shift
done


# These dependencies are installed in all the containers along with one of
# glibc-static/glibc-devel-static/libc-devel, one of which will be needed 
# to build runit. everything also gets `tzdata`, except suse which gets
# timezone and gzip
dependencies="bzip2 chrpath curl gcc gzip lshw lsof make net-tools numactl sysstat tar"

# Set up vars and defaults
workdir=${workdir:-/tmp/cluster-setup-files}
mkdir -p ${workdir}
cluster_prefix=${cluster_prefix:-sandbox}
cluster_name=cluster
restart_policy=${restart_policy:-unless-stopped}
compose_file="${workdir}/${cluster_prefix}_${cluster_name}.yml"
edition=${edition:-enterprise}
base_image=${base_image:-ubuntu:18.04}
username=${username:-Administrator}
password=${password:-password}
cidr_block=${cidr_block:-172.18.0.0/16}
services=${services:-data,index,query,eventing,fts}
[ "${nodes}" = "" ] && nodes=(master:172.18.0.2 node1:172.18.0.3 node2:172.18.0.4 node3:172.18.0.5)
node_names="$(for node in ${nodes[@]:1}; do printf "$(echo $node | sed 's/\:.*//') "; done)"
master_name=$(echo ${nodes[0]} | sed 's/\:.*//')
num_nodes=${#nodes[@]}

# Copy files to ${workdir}
cp -rp files ${workdir}/.

if [ "${version}" != "" -a "${image}" != "" ]
then
  echo "Use --version or --image, not both"
  exit 1
elif [ "${version}" != "" ]
then
  # if a version has been provided, we need build and name an image
  image="${cluster_prefix}_${cluster_name}"
else
  image=${image:-couchbase:latest}
fi

distro_name=$(echo $base_image | cut -d: -f1)
distro_vers=$(echo $base_image | cut -d: -f2)

# Figure out the os component for our package names - there's not a 1:1 match 
# with image names. 
if [ "${distro_name}" = "amazonlinux" ]
then 
  os=amzn${distro_vers}
elif [ "${distro_name}" = "oraclelinux" ]
then
  os=oel${distro_vers}
elif [ "${distro_name}" = "opensuse/leap" ]
then
  distro_vers=15
  os=suse${distro_vers}
else
  os=${distro_name}${distro_vers}
fi
package_path="${workdir}/packages/${version}/${build}/${os}"


# The official container image uses runit which isn't available in the standard 
# package repositories for all platforms. Rather than remove runit, I've opted
# to build it, but this needs either glibc-static, glibc-devel-static or libc-dev,
# depending on the distro
if [ "${distro_name}" = "centos" ]
then
  dependencies="${dependencies} glibc-static"
  if  [ "${distro_vers}" = "8" ]
  then
    enabled_repos="--enablerepo=PowerTools"
  fi
elif [ "${distro_name}" = "oraclelinux" ]
then
  dependencies="${dependencies} glibc-static"
  if [ "${distro_vers}" = "8" ]
  then
    enabled_repos="--enablerepo=ol8_codeready_builder"
  else
    enabled_repos="--enablerepo=ol7_optional_latest"
  fi
elif [ "${distro_name}" = "opensuse/leap" ]
then
  dependencies="${dependencies} glibc-devel-static"
elif [ "${distro_name}" = "ubuntu" ]
then
  dependencies="${dependencies} libc-dev"
elif [ "${distro_name}" = "amazonlinux" ]
then
  dependencies="${dependencies} glibc-static"
fi

# These are the only other places the build really differs between distros.
case ${distro_name} in
  opensuse/leap)
    cb_package=couchbase-server-${edition}-${version}-${build}-${os}.x86_64.rpm
    dependencies="${dependencies} timezone"
    snippet_install_deps="RUN set -x \
        && zypper install -y \${DEPENDENCIES}"
    snippet_install_couchbase="RUN set -x \
        && rpm -i ./\$CB_PACKAGE"
    ;;
  debian|ubuntu)
    cb_package=couchbase-server-${edition}_${version}-${build}-${os}_amd64.deb
    dependencies="${dependencies} tzdata"
    snippet_install_deps="RUN set -x \
        && apt-get update \
        && apt-get install -yq \${DEPENDENCIES} \
        && apt-get autoremove && apt-get clean \
        && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*"
    snippet_install_couchbase="RUN set -x \
        && export INSTALL_DONT_START_SERVER=1 \
        && apt install -y ./\$CB_PACKAGE \
        && rm -f ./\$CB_PACKAGE"
    ;;
  amazonlinux|centos|oraclelinux|redhat)
    dependencies="${dependencies} tzdata"
    snippet_install_deps="RUN set -x \
        && yum install ${enabled_repos} -y \${DEPENDENCIES}"
    snippet_install_couchbase="RUN set -x \
        && export INSTALL_DONT_START_SERVER=1 \
        && yum install -y ./\$CB_PACKAGE \
        && rm -f ./\$CB_PACKAGE"
    cb_package=couchbase-server-${edition}-${version}-${build}-${os}.x86_64.rpm
    ;;
esac

# If we're building from ${VERSION}-${BUILD} we'll need a dockerfile. Much of this
# was lifted from the official dockerfile and tweaked to work with other base images
# most notably by building runit, since it's not available in all distros'
# core repos
read -r -d '' DOCKERFILE <<-DOCKERFILE || :
FROM ${base_image}
ENV CB_PACKAGE=${cb_package}
ENV PATH=\$PATH:/opt/couchbase/bin:/opt/couchbase/bin/tools:/opt/couchbase/bin/install
ENV DEPENDENCIES="${dependencies}"
COPY files/.ssh /root/.ssh
RUN set -x \
    && yum install -y vim \
    && yum install -y openssh-server openssh-clients \
    && sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/g' /etc/ssh/sshd_config

COPY ${cb_package} /app/
WORKDIR /app
${snippet_install_deps}
RUN set -x \
    && mkdir -p /package \
    && chmod 1755 /package \
    && cd /package \
    && curl -LO http://smarden.org/runit/runit-2.1.2.tar.gz \
    && gunzip runit-2.1.2.tar \
    && tar -xpf runit-2.1.2.tar \
    && rm runit-2.1.2.tar \
    && cd admin/runit-2.1.2 \
    && package/install
RUN if [ ! -x /usr/sbin/runsvdir-start ]; then \
        cp -a /package/admin/runit-2.1.2/etc/2 /usr/sbin/runsvdir-start; \
    fi
RUN groupadd -g 1000 couchbase && useradd couchbase -u 1000 -g couchbase -M
${snippet_install_couchbase}
RUN mkdir -p /service/couchbase-server && printf "#!/bin/sh \\\n \\
    cd /opt/couchbase \\\n \\
    mkdir -p var/lib/couchbase  \\\n \\
    var/lib/couchbase/config  \\\n \\
    var/lib/couchbase/data  \\\n \\
    var/lib/couchbase/stats  \\\n \\ 
    var/lib/couchbase/logs  \\\n \\
    var/lib/moxi  \\\n \\
    chown -R couchbase:couchbase var  \\\n \\
    if [ "\$(whoami)" = "couchbase" ]; then  \\\n \\
    exec /opt/couchbase/bin/couchbase-server -- -kernel global_enable_tracing false -noinput  \\\n \\
    else  \\\n \\
      exec chpst -ucouchbase  /opt/couchbase/bin/couchbase-server -- -kernel global_enable_tracing false -noinput  \\\n \\
    fi" > /service/couchbase-server/run
RUN chmod +x /service/couchbase-server/run
RUN chown -R couchbase:couchbase /service
RUN printf "#!/bin/sh \\\n \\
\\\n \\
echo \"Running in Docker container - \$0 not available\"" > /usr/local/bin/dummy.sh
# Add dummy script for commands invoked by cbcollect_info that
# make no sense in a Docker container
RUN ln -s dummy.sh /usr/local/bin/iptables-save && \
    ln -s dummy.sh /usr/local/bin/lvdisplay && \
    ln -s dummy.sh /usr/local/bin/vgdisplay && \
    ln -s dummy.sh /usr/local/bin/pvdisplay
  
# Fix curl RPATH
RUN chrpath -r '\$ORIGIN/../lib' /opt/couchbase/bin/curl
RUN printf "#!/bin/bash \\\n \\
set -e \\\n \\
\\\n \\
#run sshd in backgroup \\n \

ssh-keygen -A \\n \
nohup /usr/sbin/sshd -D & > /var/log/sshd.log 2>&1  \\n \
\\\n \\
#starting couchbase server \\n \
staticConfigFile=/opt/couchbase/etc/couchbase/static_config \\\n \\
restPortValue=8091 \\\n \\
\\\n \\
# see https://developer.couchbase.com/documentation/server/current/install/install-ports.html \\\n \\
overridePort() { \\\n \\
    portName=\\\$1 \\\n \\
    portNameUpper=\\\$(echo \\\$portName | awk '{print toupper(\\\$0)}') \\\n \\
    portValue=\\\${!portNameUpper} \\\n \\
\\\n \\
    # only override port if value available AND not already contained in static_config \\\n \\
    if [ \"\\\$portValue\" != \"\" ]; then \\\n \\
        if grep -Fq \"{\\\${portName},\" \\\${staticConfigFile} \\\n \\
        then \\\n \\
            echo \"Don't override port \\\${portName} because already available in \\\$staticConfigFile\" \\\n \\
        else \\\n \\
            echo \"Override port '\\\$portName' with value '\\\$portValue'\" \\\n \\
            echo \"{\\\$portName, \\\$portValue}.\" >> \\\${staticConfigFile} \\\n \\
\\\n \\
            if [ \\\${portName} == \"rest_port\" ]; then \\\n \\
                restPortValue='\\\${portValue}' \\\n \\
            fi \\\n \\
        fi \\\n \\
    fi \\\n \\
} \\\n \\
\\\n \\
overridePort \"rest_port\" \\\n \\
overridePort \"mccouch_port\" \\\n \\
overridePort \"memcached_port\" \\\n \\
overridePort \"query_port\" \\\n \\
overridePort \"ssl_query_port\" \\\n \\
overridePort \"fts_http_port\" \\\n \\
overridePort \"moxi_port\" \\\n \\
overridePort \"ssl_rest_port\" \\\n \\
overridePort \"ssl_capi_port\" \\\n \\
overridePort \"ssl_proxy_downstream_port\" \\\n \\
overridePort \"ssl_proxy_upstream_port\" \\\n \\
\\\n \\
\\\n \\
[[ \"\\\$1\" == \"couchbase-server\" ]] && { \\\n \\
\\\n \\
    if [ \"\\\$(whoami)\" = \"couchbase\" ]; then \\\n \\
        # Ensure that /opt/couchbase/var is owned by user 'couchbase' and \\\n \\
        # is writable \\\n \\
        if [ ! -w /opt/couchbase/var -o \"\\\$(find /opt/couchbase/var -maxdepth 0 -printf '%%u')\" != \"couchbase\" ]; then \\\n \\
            echo \"/opt/couchbase/var is not owned and writable by UID 1000\" \\\n \\
            echo \"Aborting as Couchbase Server will likely not run\" \\\n \\
            exit 1 \\\n \\
        fi \\\n \\
    fi \\\n \\
    echo \"Starting Couchbase Server -- Web UI available at http://<ip>:\\\$restPortValue\" \\\n \\
    echo \"and logs available in /opt/couchbase/var/lib/couchbase/logs\" \\\n \\
    exec /usr/sbin/runsvdir-start \\\n \\
}\\\n \\
\\\n \\

exec \"\\\@\"" > /entrypoint.sh
RUN chmod a+x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

CMD ["couchbase-server"]
# 22: ssh port
# 8091: Couchbase Web console, REST/HTTP interface
# 8092: Views, queries, XDCR
# 8093: Query services (4.0+)
# 8094: Full-text Search (4.5+)
# 8095: Analytics (5.5+)
# 8096: Eventing (5.5+)
# 11207: Smart client library data node access (SSL)
# 11210: Smart client library/moxi data node access
# 11211: Legacy non-smart client library data node access
# 18091: Couchbase Web console, REST/HTTP interface (SSL)
# 18092: Views, query, XDCR (SSL)
# 18093: Query services (SSL) (4.0+)
# 18094: Full-text Search (SSL) (4.5+)
# 18095: Analytics (SSL) (5.5+)
# 18096: Eventing (SSL) (5.5+)
EXPOSE 22 8091 8092 8093 8094 8095 8096 11207 11210 11211 18091 18092 18093 18094 18095 18096
# VOLUME /opt/couchbase/var

DOCKERFILE

write_dockerfile() {
  if [ "${debug}" = "true" ]; then printf "#Dockerfile\n${DOCKERFILE}\n"; fi
  echo "$DOCKERFILE" > ${workdir}/Dockerfile
}

get_package() {
  package_base_url="http://latestbuilds.service.couchbase.com/builds/latestbuilds/couchbase-server/zz-versions/${version}/${build}"
  (
    cd "${workdir}"
    if [ ! -e "${workdir}/${cb_package}" ]
    then
      echo "Downloading installation package: ${package_base_url}/${cb_package}"
      curl -fLo "${workdir}/${cb_package}" "${package_base_url}/${cb_package}"
    fi
  )
}

build_image() {
  (
    cd "${workdir}"
    if docker image ls | grep -w "${image}" &>/dev/null; then echo "Removing previous image ${image}:" && docker rmi "${image}"; fi
    docker build ${workdir} -f ${workdir}/Dockerfile -t "${image}"
  )
}

if [ "${debug}" = "true" ]; then debug "Creating a ${num_nodes} cluster" && debug "Nodes: ${nodes[@]}"; fi

if [ "${cpu_limit}" != "" ]
then
    cpu_limit="cpus: ${cpu_limit}"
fi

if [ "${mem_limit}" != "" ]
then
    mem_limit="mem_limit: ${mem_limit}"
fi

fatal() {
    echo
    echo "Errors occurred:"
    printf "$@$errors\n\n"
    exit 1
}

error() {
    errors="$errors    $@\n"
}

command -v docker &>/dev/null || error "docker not found"
command -v docker-compose &> /dev/null || error "docker-compose not found"

[ "$errors" != "" ] && fatal

get_node() {
    node=(${nodes[$1]//:/ })
    name=${node[0]}
    ip=${node[1]}
    ports=""
    if [ $1 = 0 ]
    then
        ports="ports:
        - \"8091-8094:8091-8094\"
        - \"11210:11210\""
    fi
    networks="networks:
          ${cluster_name}:
            ipv4_address: ${ip}"
    echo "      $name:
        image: ${image}
        restart: ${restart_policy}"
    [ "${cpu_limit}" != "" ] && echo "        ${cpu_limit}"
    [ "${mem_limit}" != "" ] && echo "        ${mem_limit}"
    [ "$ports" != "" ] && echo "        $ports"
    echo "        $networks"
}

export -f get_node

docker_compose() {
  # handles creating both the compose file, and the base image if required
  cat <<-EOF > ${compose_file}
version: "2.4"
services:
$(for i in $(seq 0 $(($num_nodes-1))); do get_node $i; done)
networks:
    ${cluster_name}:
        ipam:
            config:
                - subnet: ${cidr_block}
EOF
  if [ "$debug" = "true" ]; then echo "# DEBUG: compose file" && cat "${compose_file}"; fi
  case "$1" in
  "up")
      if [ "${version}" != "" ]
      then
        execute write_dockerfile
        execute get_package
        execute build_image
      fi
      execute docker-compose -f ${compose_file} -p ${cluster_prefix} up -d --remove-orphans || error "Couldn't start containers"
      ;;
  "down")
      execute docker-compose -f ${compose_file} -p ${cluster_prefix} down -v --remove-orphans || error "Couldn't stop containers"
      ;;
  esac
  if [ "$errors" != "" ]; then fatal; fi
}

case "${action}" in
    "up")
        cluster_present=true
        for node in ${master_name} ${node_names}
        do
          if ! docker ps | grep ${cluster_prefix}_${node}_1 &>/dev/null; then cluster_present=false; fi
        done
        if [ ${cluster_present} = false ]
        then
          docker_compose up
        # fi
          (
            echo docker exec -i ${cluster_prefix}_${master_name}_1 bash
            execute docker exec -i ${cluster_prefix}_${master_name}_1 bash -s <<-EOF || error "cluster bootstrap failed"
                initialised=false
                sleep 30
                for i in {1..60}
                do
                    printf "Initialising cluster ... "
                    init_output=\$(couchbase-cli cluster-init --cluster localhost --cluster-username ${username} \
                        --cluster-password ${password} --cluster-port 8091 \
                        --cluster-name ${cluster_name} \
                        --services ${services} 2>&1)
                    result=\$?
                    [ "${debug}" = "true" ] && echo "\${init_output}"
                    [ "\${result}" = "0" ] && initialised=true && echo "\${init_output}"&& break || printf "Retrying ... \n" && sleep 10               
                done
                [ "\$initialised" = "false" ] && echo "Something broke - try again with --debug to look for clues: ${init_output}" && exit 1
                for node in ${node_names[@]}; do
                    (
                        for i in {1..60}
                        do
                            host=${cluster_prefix}_\${node}_1.${cluster_prefix}_${cluster_name}
                            add_output=\$(couchbase-cli server-add --cluster localhost:8091 --username ${username} --password ${password} --server-add=\$host --server-add-username=${username} --server-add-password="${password}" --services ${services})
                            result=\$?
                            [ "${debug}" = "true" ] && echo "Adding \${node} ... \${add_output}"
                            [ "\${result}" = "0" ] && echo "Adding \${node} ... \${add_output}" && break || sleep 10  
                        done
                        # [ "\$added" = "false" ] && echo "Something broke - try again with --debug to look for clues: ${add_output}" && exit 1
                    ) &
                done
                wait
                printf "Rebalancing ... "
                couchbase-cli rebalance --no-progress-bar --cluster localhost:8091 --username ${username} \
                    --password ${password} || exit 1
EOF
          )
          printf "\nCluster is using image ${image}\n\n            url: http://localhost:8091\n\n"
          if [ "${version}" != "" ]
          then
            echo "The image '${image}' was built using ${workdir}/Dockerfile"
          fi
          if [ "${save_file}" != "" ]
          then 
            echo
            echo "You can control the containers via docker compose with, e.g." 
            echo "  docker-compose -f ${save_file} -p ${cluster_prefix} stop"
          else
            echo "The compose file used to create this cluster was: ${compose_file}"
            echo
            echo "Take a copy of these if you want to be able to control this cluster with docker-compose"
          fi
        else
          printf "Looks like ${cluster_prefix}_${master_name} is running, do you need to run cluster-setup down first?\n"
        fi
        ;;
    "down")
        execute docker_compose down
        ;;
    *)
        help
        ;;
esac
