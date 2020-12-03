package com.couchbase;

import com.couchbase.client.java.Cluster;
import com.couchbase.client.java.Collection;
import com.couchbase.client.java.json.JsonObject;
import com.couchbase.transactions.TransactionGetResult;
import com.couchbase.transactions.Transactions;
import com.couchbase.transactions.config.TransactionConfigBuilder;
import com.couchbase.transactions.error.TransactionFailed;


public class transaction {
    private final static String CONTENT_NAME= "content";
    private final static String CLUSTER_LOGIN_USERNAME= "Administrator";
    private final static String CLUSTER_LOGIN_PASSWORD= "password";
    private final static JsonObject INITIAL = JsonObject.create().put(CONTENT_NAME, "initial");
    private final static JsonObject UPDATED = JsonObject.create().put(CONTENT_NAME, "updated");

    private static String clusterIP;

    public static void main(String[] args)  {
      //  String randomId = UUID.randomUUID().toString();
        String docId = null;
        String operation = "insert";
        for(String parameter : args) {
            switch (parameter.split("=")[0].toLowerCase()) {
                case "clusterip":
                    clusterIP= parameter.split("=")[1];
                    break;
                case "operation":
                    operation = parameter.split("=")[1];
                    break;
                case "docid":
                    docId = parameter.split("=")[1];
                    break;
                default:
                    System.out.println("Unknown parameter is given as input. Exiting");
                    Usage();
                    System.exit(-1);
            }
        }


        try{

            //Cluster on which transactions are to be executed
            Cluster cluster = Cluster.connect(clusterIP, CLUSTER_LOGIN_USERNAME, CLUSTER_LOGIN_PASSWORD);

            //Collection in which transactions will be executed
            Collection collectionForTxnOperations = cluster.bucket("default").defaultCollection();

            TransactionConfigBuilder builder = TransactionConfigBuilder.create();  // Default transaction Configuration
            Transactions transactions = Transactions.create(cluster, builder);  // Transaction factory with default config is created on the cluster
            String finalOperation = operation;
            String finalDocId = docId;
           /* if(finalOperation.equals("insert")){
                finalDocId = randomId;
            }*/

            transactions.run((ctx) -> {
                TransactionGetResult result ;
                switch(finalOperation){
                    case "insert":
                        ctx.insert(collectionForTxnOperations,finalDocId,INITIAL);
                        break;
                    case "get":
                        ctx.get(collectionForTxnOperations, finalDocId);
                        break;
                    case "getoptional":
                        ctx.getOptional(collectionForTxnOperations, finalDocId);
                        break;
                    case "replace":
                        result =  ctx.get(collectionForTxnOperations, finalDocId);
                        ctx.replace(result,UPDATED);
                        break;
                    case "remove":
                        result =  ctx.get(collectionForTxnOperations, finalDocId);
                        ctx.remove(result);
                        break;
                    case "commit":
                        ctx.commit();
                        break;
                    case "rollback":
                        ctx.rollback();
                        break;
                }
            });
        } catch(TransactionFailed e) {
            System.out.println("Exception occurred while executing the transaction:" + e.getMessage());
            System.exit(-1);
        }catch(Exception e){
            e.printStackTrace();
            System.exit(-1);
        }
    }

    private static void Usage(){
        System.out.println("\n Usage: \n");
        System.out.println("Please enter the command in below format: \n");
        System.out.println("java -cp <Relative location to this Jar> com.couchbase.transaction  clusterIp=<YourClusterIp> operation=<RequiredTransactionOperation> docId=<DocumentId>  \n");
    }
}
