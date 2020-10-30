README.TXT

A simple, flexible handy test Couchbase tool
   - Manage scopes, collections
   - Load and drop documents

Flexible:
 o Add a new method with Properties object as parameter in the main class or any other java class (uses java reflection)
 o Simply run as below with set of methods to execute:
   -Drun=<method>,<method>

Usage:

$ mvn clean package


To create 1000 documents in default bucket, default scope, default collection (default._default._default):
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=18091 -Dkvport=11207 -Dtls=true -Drun=connectCluster,createDocs -Ddoc.count=1000  -Doperation=create -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar
(or)
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=8091 -Dkvport=11210 -Drun=connectCluster,createDocs -Ddoc.count=1000  -Doperation=create -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar

To create 10 scopes (project_1,..project_10) of bucket (db):
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=18091 -Dkvport=11207 -Dtls=true -Drun=connectCluster,createScopes -Dbucket=db -Dscope=project -Dscope.count=10 -Doperation=create -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar

To create 100 tenants (tenant_1,tenant_2..tenant_100) in each of 10 scopes (project_1,..project_10) of bucket (db):
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=18091 -Dkvport=11207 -Dtls=true -Drun=connectCluster,createCollections -Dbucket=db -Dscope=project -Dscope.count=10 -Dcollection=tenant -Dcollection.count=100 -Doperation=create -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar

To create 1000 documents in each of 100 tenants (tenant_1,tenant_2..tenant_100) in each of 10 scopes (project_1,..project_10) of bucket (db):
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=18091 -Dkvport=11207 -Dtls=true -Drun=connectCluster,createTenantDocs -Dbucket=db -Dscope=project -Dscope.count=10 -Ddoc.count=1000 -Dcollection=tenant -Dcollection.count=100 -Doperation=create -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar

To create a cycle with 1 bucket with 200MB quota, 10 scopes/bucket, 100 tenants/scope, 1 document/tenant:
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=18091 -Dkvport=11207 -Dtls=true -Drun=cycle -Dbucket=db_1 -Dscope="project" -Dscope.count=10 -Dcollection=tenant -Dcollection.count=100 -Ddoc.count=1 -Dbucket.quota=200 -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar
where cycle == connectClusterOnly,createBuckets,delay,openBucket,createScopes,createCollections,listCollections,createTenantDocs

java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=18091 -Dkvport=11207 -Dtls=true -Drun=cycle -Dbucket=db_1 -Dscope="project" -Dscope.count=10 -Dcollection=tenant -Dcollection.count=100 -Ddoc.count=1 -Dbucket.quota=100 -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar

java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Dport=18091 -Dkvport=11207 -Dtls=true -Drun=cycle -Dbucket=db_1 -Dscope="project" -Dscope.count=10 -Dcollection=tenant -Dcollection.count=100 -Ddoc.count=1 -Dtls=true -Dbucket.quota=100 -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar

To run queries:
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Drun=connectClusterOnly,query,analytics  -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar 
$ java -Durl=172.23.96.189 -Duser=Administrator -Dpassword=password -Drun=connectClusterOnly,query,analytics  -Dquery='SELECT * FROM Metadata.`Dataverse`' -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar

To delete, use the below in the above commands. To drop all buckets or collections, use -Doperation=dropall
-Doperation=drop

Cloud instance:
$ java -Durl=d6965adb-6174-4a45-91e7-866f4bf9b408.dataplane.nonprod-project-avengers.com -Ddbaas=true -Duser=dbtestuser -Dpassword=password -Drun=connectCluster,pingCluster,qryGreeting,createDocs -Dbucket=couchbasecloudbucket -jar target/cbpowertool-0.0.1-SNAPSHOT-jar-with-dependencies.jar
