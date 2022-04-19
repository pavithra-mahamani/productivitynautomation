#!/bin/bash

for j in {1..50}
do
curl -XPUT -H "Content-Type: application/json" \
-u Administrator:password http://172.23.121.59:8094/api/index/default2-index$j -d \
'{
  "type": "fulltext-index",
  "name": "default1",
  "sourceType": "couchbase",
  "sourceName": "default2",
  "planParams": {
    "maxPartitionsPerPIndex": 171,
    "indexPartitions": 6
  },
  "params": {
    "doc_config": {
      "docid_prefix_delim": "",
      "docid_regexp": "",
      "mode": "type_field",
      "type_field": "type"
    },
    "mapping": {
      "analysis": {},
      "default_analyzer": "standard",
      "default_datetime_parser": "dateTimeOptional",
      "default_field": "_all",
      "default_mapping": {
        "dynamic": false,
        "enabled": true,
        "properties": {
          "rsx": {
            "dynamic": false,
            "enabled": true,
            "fields": [
              {
                "index": true,
                "name": "rsx",
                "type": "text"
              }
            ]
          }
        }
      },
      "default_type": "_default",
      "docvalues_dynamic": true,
      "index_dynamic": true,
      "store_dynamic": false,
      "type_field": "_type"
    },
    "store": {
      "indexType": "scorch"
    }
  },
  "sourceParams": {}
}'

curl -XDELETE -H "Content-Type: application/json" -u Administrator:password http://172.23.121.59:8094/api/index/default2-index$j
done


for j in {1..50}
do
curl -XPUT -H "Content-Type: application/json" \
-u Administrator:password http://172.23.121.59:8094/api/index/default1-index$j -d \
'{
  "type": "fulltext-index",
  "name": "default1",
  "sourceType": "couchbase",
  "sourceName": "default1",
  "planParams": {
    "maxPartitionsPerPIndex": 171,
    "indexPartitions": 6
  },
  "params": {
    "doc_config": {
      "docid_prefix_delim": "",
      "docid_regexp": "",
      "mode": "type_field",
      "type_field": "type"
    },
    "mapping": {
      "analysis": {},
      "default_analyzer": "standard",
      "default_datetime_parser": "dateTimeOptional",
      "default_field": "_all",
      "default_mapping": {
        "dynamic": false,
        "enabled": true,
        "properties": {
          "rsx": {
            "dynamic": false,
            "enabled": true,
            "fields": [
              {
                "index": true,
                "name": "rsx",
                "type": "text"
              }
            ]
          }
        }
      },
      "default_type": "_default",
      "docvalues_dynamic": true,
      "index_dynamic": true,
      "store_dynamic": false,
      "type_field": "_type"
    },
    "store": {
      "indexType": "scorch"
    }
  },
  "sourceParams": {}
}'

curl -XDELETE -H "Content-Type: application/json" -u Administrator:password http://172.23.121.59:8094/api/index/default1-index$j
done



for j in {1..50}
do
curl -XPUT -H "Content-Type: application/json" \
-u Administrator:password http://172.23.121.59:8094/api/index/default3-index$j -d \
'{
  "type": "fulltext-index",
  "name": "default1",
  "sourceType": "couchbase",
  "sourceName": "default3",
  "planParams": {
    "maxPartitionsPerPIndex": 171,
    "indexPartitions": 6
  },
  "params": {
    "doc_config": {
      "docid_prefix_delim": "",
      "docid_regexp": "",
      "mode": "type_field",
      "type_field": "type"
    },
    "mapping": {
      "analysis": {},
      "default_analyzer": "standard",
      "default_datetime_parser": "dateTimeOptional",
      "default_field": "_all",
      "default_mapping": {
        "dynamic": false,
        "enabled": true,
        "properties": {
          "rsx": {
            "dynamic": false,
            "enabled": true,
            "fields": [
              {
                "index": true,
                "name": "rsx",
                "type": "text"
              }
            ]
          }
        }
      },
      "default_type": "_default",
      "docvalues_dynamic": true,
      "index_dynamic": true,
      "store_dynamic": false,
      "type_field": "_type"
    },
    "store": {
      "indexType": "scorch"
    }
  },
  "sourceParams": {}
}'

curl -XDELETE -H "Content-Type: application/json" -u Administrator:password http://172.23.121.59:8094/api/index/default3-index$j
done
