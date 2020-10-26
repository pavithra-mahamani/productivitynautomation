# Couchbase Query Prometheus Exporter

This python service exposes a /metrics endpoint to be used in Prometheus.

These metrics are defined in queries.json and define which queries should be exposed as metrics

The structure of queries.json is

```json
{
  // map of cluster name to cluster options
  "clusters": {},
  // array of queries to be exposed
  "queries": []
}
```

Cluster options:

```json
{
  "host": "<couchbase cluster host>",
  "username": "<couchbase username>",
  "password": "<couchbase password>"
}
```

Query:

```json
{
  "name": "<metric name>",
  "cluster": "<cluster name defined in clusters map>",
  "query": "<couchbase query to perform>",
  "description": "<description of the metric>",
  "value_key": "<which column should be used as the value for the metric>",
  // labels are columns that are exposed as labels
  "labels": ["<column name>"]
}
```
