# This repository contains the Engineering productivity automation helperscripts

Some of the key tools:

1. Run Analyzer Tool 
Usage: go run runanalyzer/runanalyzer.go --action help
Enter action value. 
-action lastaborted 6.5.0-4106 6.5.0-4059 6.5.0-4000  : to get the aborted jobs common across last 3 builds. Options: --cbrelease [6.5]specificbuilds --limits 3 --qryfilter 'where numofjobs>900' 
-action savejoblogs 6.5.0-4106  : to download the jenkins logs and save in S3 for a given build. Options: --dest [local]|s3|none --src csvfile --os centos --overwrite [no]|yes --updateurl [no]|yes --includes [console,config,parameters,testresult],archive--s3bucket cb-logs-qe --s3url http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/ --cbqueryurl [http://172.23.109.245:8093/query/service]
-action totaltime 6.5  : to get the total number of jobs, time duration for a given set of  builds in a release, Options: --limits [100] --qryfilter 'where result.numofjobs>900 and (totalcount-failcount)*100/totalcount>90'
-action getrunprogress build : to get the summary report on the kickedoff runs for a build.  Options: --reqserverpools=[regression,durability,ipv6,ipv6-raw,ipv6-fqdn,ipv6-mix,jre-less,jre,security,elastic-fts,elastic-xdcr] --reqstates=[available,booked] 
-action runquery 'select * from server where lower(`os`)="centos" and `build`="6.5.0-4106"' : to run a given query statement 
-action runupdatequery --cbqueryurl 'http://172.23.105.177:8093/query/service'  "update \`QE-server-pool\` set state='available' where ipaddr='172.23.120.240'" : to run a given update query statement
-action setpoolipstate state ips : to set given state for the given ips (separated by comma)
-action getpoolipstate ips : to get state for given ips (separated by comma)


2. System health

*** Helper Tool ***
Usage: go run syshealth/syshealthmonitor.go -h | --help 
Enter action value. 
-action runquery 'select * from server where lower(`os`)="centos" and `build`="6.5.0-4106"' : to run a given query statement
-action getserverpoolhosts : to get the server pool host ips
-action getserverpoolinfo filename : to get the server pool info for given ips list file
-action healthchecks : to assess the VMs health


$ syshealth/gen_summary_qe_pools_only.sh
Usage syshealth/gen_summary_qe_pools_only.sh os used_pools_file
Example: syshealth/gen_summary_qe_pools_only.sh linux_or_centos_or_comma_listed_platforms file
Example: syshealth/gen_summary_qe_pools_only.sh linux file
Example: syshealth/gen_summary_qe_pools_only.sh centos,suse12 file

$ syshealth/gen_healthsummary.sh 
Usage syshealth/gen_healthsummary.sh ips_or_file
Example: syshealth/gen_healthsummary.sh ip1,ip2,ip3

