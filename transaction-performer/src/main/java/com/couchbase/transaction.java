package com.couchbase;

import java.util.UUID;

import com.couchbase.client.java.Cluster;
import com.couchbase.client.java.Collection;
import com.couchbase.client.java.json.JsonObject;
import com.couchbase.client.java.json.JsonArray;
import com.couchbase.transactions.TransactionGetResult;
import com.couchbase.transactions.Transactions;
import com.couchbase.transactions.config.TransactionConfigBuilder;
import com.couchbase.transactions.error.TransactionFailed;


public class transaction {
    private final static String CONTENT_NAME= "content";
    private final static String CLUSTER_LOGIN_USERNAME= "Administrator";
    private final static String CLUSTER_LOGIN_PASSWORD= "password";
    //private final static JsonObject INITIAL;
    //private final static JsonObject UPDATED = JsonObject.create().put(CONTENT_NAME, "updated");
    private static JsonObject doccontent = JsonObject.create();
    private static String clusterIP;
    private static String bucket;
    private static String docstring;
    private static String[] docidArray;
    private static String[] removeDocidArray;
    private static String temp_str;
    private static JsonObject temp_obj;
    private static String removeDocIds;
 
    public static void main(String[] args)  {
        String randomId = UUID.randomUUID().toString();
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
                    docidArray = docId.split(",");
                    break;
                case "removedocids":
                    removeDocIds = parameter.split("=")[1];
                    removeDocidArray = removeDocIds.split(",");
                    break;
                case "bucket":
                	bucket = parameter.split("=")[1];
                	break;
                case "doccontent":
                	docstring = parameter.split("=")[1];
                	doccontent = JsonObject.fromJson(docstring);              	
                	break;
                default:
                    System.out.println("Unknown parameter is given as input. Exiting" + parameter);
                    Usage();
                    System.exit(-1);
            }
        }
        if(doccontent.isEmpty()) {
        	doccontent = JsonObject.create().put(CONTENT_NAME, "initial");
        	doccontent.put("id", randomId);
        }

        try{

            //Cluster on which transactions are to be executed
            Cluster cluster = Cluster.connect(clusterIP, CLUSTER_LOGIN_USERNAME, CLUSTER_LOGIN_PASSWORD);

            //Collection in which transactions will be executed
            Collection collectionForTxnOperations = cluster.bucket(bucket).defaultCollection();

            TransactionConfigBuilder builder = TransactionConfigBuilder.create();  // Default transaction Configuration
            Transactions transactions = Transactions.create(cluster, builder);  // Transaction factory with default config is created on the cluster
            String[] operationList = operation.split(",");
            String finalDocId = docId;
            
           /* if(finalOperation.equals("insert")){
                finalDocId = randomId;
            }*/
            
            transactions.run((ctx) -> {
                TransactionGetResult result ;
                for(int j=0;j<operationList.length;j++) {
                switch(operationList[j]){
                    case "insert":
                    	for(int i=0; i<docidArray.length; i++) {
                    		doccontent.put("id", docidArray[i]);
                        	doccontent.put("content", "doc_content"+docidArray[i]);
                    		ctx.insert(collectionForTxnOperations,docidArray[i],doccontent);
                    	}	
                        break;
                    case "get":
                        ctx.get(collectionForTxnOperations, finalDocId);
                        result = ctx.get(collectionForTxnOperations, finalDocId);
                        System.out.println("get of doc is " + result);
                        break;
                    case "getoptional":
                        ctx.getOptional(collectionForTxnOperations, finalDocId);
                        break;
                    case "replace":
                    	for(int i=0; i<docidArray.length; i++) {	
                    		result =  ctx.get(collectionForTxnOperations, docidArray[i]);
                    		temp_obj = result.contentAsObject();
                    		temp_str = temp_obj.get("id").toString();
                    		temp_obj.put("id", temp_str+"_updated");
                    		temp_str = temp_obj.get("content").toString();
                    		temp_obj.put("content", temp_str+"_updated");
                            ctx.replace(result,temp_obj);
                    	}         
                        break;
                    case "remove":
                    	for(int i=0; i<removeDocidArray.length; i++) {	
                    		result =  ctx.get(collectionForTxnOperations, removeDocidArray[i]);
                    		ctx.remove(result);
                    	}    
                        break;
                    case "commit":
                        ctx.commit();
                        break;
                    case "rollback":
                    	for(int i=0; i<docidArray.length; i++) {
                    		doccontent.put("id", docidArray[i]);
                        	doccontent.put("content", "doc_content"+docidArray[i]);
                    		ctx.insert(collectionForTxnOperations,docidArray[i],doccontent);
                    	}
                        ctx.rollback();
                        break;
                    
                }
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
