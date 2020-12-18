package com.couchbase;

import java.util.ArrayList;
import java.util.UUID;

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
    private static JsonObject doccontent = JsonObject.create();
    private static String clusterIP;
    private static String bucket;
    private static String docstring;
    private static ArrayList<String> operationList = new ArrayList<String>();;
    private static String temp_str;
    private static JsonObject temp_obj;
    private static String[] optDocidArray;
    private static String operationDocids;
    private static ArrayList<TxnOperationId> txnOptObj = new ArrayList<TxnOperationId>();
    private static TxnOperationId txnobj;
    private static  String opt;
    private static  String optDocid;
    
   
    public static void main(String[] args)  {
        String randomId = UUID.randomUUID().toString();
        String docId = null;
        for(String parameter : args) {
			switch (parameter.split("=")[0].toLowerCase()) {
                case "clusterip":
                    clusterIP= parameter.split("=")[1];
                    break;
                case "operationdocids":
                    operationDocids = parameter.split("=")[1];
                    optDocidArray = operationDocids.split(",");
                    break;
                case "bucket":
                	bucket = parameter.split("=")[1];
                	break;
                case "doccontent":
                	docstring = parameter.split("=")[1];
                	doccontent = JsonObject.fromJson(docstring);              	
                	break;
                default:
                    System.out.println("Unknown parameter is given as input. Exiting " + parameter);
                    Usage();
                    System.exit(-1);
            }
        }
        if(doccontent.isEmpty()) {
        	doccontent = JsonObject.create().put(CONTENT_NAME, "initial");
        	doccontent.put("id", randomId);
        }
        
        
        for(int i=0;i<optDocidArray.length;i++) {
        	if(optDocidArray[i].contains("-")) {
        		opt = optDocidArray[i].split("-")[0];
        		if(optDocidArray[i].split("-").length>1) {
	        		if(opt.equals("insert") || opt.equals("replace") || opt.equals("remove")) {
	        			opt = optDocidArray[i].split("-")[0];
	            		optDocid = optDocidArray[i].split("-")[1];
	        		}
	        		else
	        			System.out.println("doc ids other than insert, replace and remove operatios will be ignored for other operations");
        		}
        		
        	}
        	else
        		opt = optDocidArray[i];
        	txnobj= new TxnOperationId(opt, optDocid);
        	txnOptObj.add(txnobj);
        }
        
        try{

            //Cluster on which transactions are to be executed
            Cluster cluster = Cluster.connect(clusterIP, CLUSTER_LOGIN_USERNAME, CLUSTER_LOGIN_PASSWORD);

            //Collection in which transactions will be executed
            Collection collectionForTxnOperations = cluster.bucket(bucket).defaultCollection();

            TransactionConfigBuilder builder = TransactionConfigBuilder.create();  // Default transaction Configuration
            Transactions transactions = Transactions.create(cluster, builder);  // Transaction factory with default config is created on the cluster
            
            String finalDocId = docId;
            
            transactions.run((ctx) -> {
                TransactionGetResult result ;
                for(int j=0;j<txnOptObj.size();j++) {
                switch(txnOptObj.get(j).txnOperation){
                    case "insert":                    	
                    	doccontent.put("id", txnOptObj.get(j).txnDocID);
	                    doccontent.put("content", "doc_content"+txnOptObj.get(j).txnDocID);
	                    ctx.insert(collectionForTxnOperations,txnOptObj.get(j).txnDocID,doccontent);
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
                    	result =  ctx.get(collectionForTxnOperations, txnOptObj.get(j).txnDocID);
                        temp_obj = result.contentAsObject();
                        temp_str = temp_obj.get("id").toString();
                        temp_obj.put("id", temp_str+"_updated");
                        temp_str = temp_obj.get("content").toString();
                        temp_obj.put("content", temp_str+"_updated");
                        ctx.replace(result,temp_obj);
                        break;
                    case "remove":
                    	result =  ctx.get(collectionForTxnOperations, txnOptObj.get(j).txnDocID);
                        ctx.remove(result);
                        break;
                    case "commit":
                        ctx.commit();
                        break;
                    case "rollback":
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

    private static void insert() {
    	
    }
    private static void Usage(){
        System.out.println("\n Usage: \n");
        System.out.println("Please enter the command in below format: \n");
        System.out.println("java -cp <Relative location to this Jar> com.couchbase.transaction  clusterIp=<YourClusterIp> operationDocids=<operation-docid> doccontent=<json body as string with single quotes enclosed>\n");
    }
    
    public static class TxnOperationId{
    	String txnOperation=null, txnDocID=null;
    	TxnOperationId(String txnOperation, String txnDocID){
    		this.txnOperation = txnOperation;
    		this.txnDocID = txnDocID;
    	}
    }

}

