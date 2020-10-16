# Grafana Dashboard Automation

This python service provides an API for programatically creating grafana dashboards. It also acts as a proxy between grafana and your data to allow grafana to use a JSON or CSV file or a Couchbase bucket as a data source.

# Requirements

- Python 3
- Pip
- Grafana
- Grafana JSON plugin

# Setup Grafana

Install grafana https://grafana.com/docs/grafana/latest/installation/ and setup a username and password

Install the JSON plugin https://grafana.com/grafana/plugins/simpod-json-datasource/installation

# Run the service

The only command line argument is the connection string for grafana in the format of username:password@host:port

```
pip install -r requirements.txt
python dashboard.py http://admin:password@127.0.0.1:3000
```

The API is now listening on port 5000

# Using the API

The only relevant endpoint is /add which is used to add data sources and Grafana dashboards. For any request you don't understand it may be useful to view the next section which contains a comprehensive example

A request should be in this format:

```json
{
  "dashboard_title": "",
  "data": [],
  "grafana": []
}
```

Each item in the data array should be formatted as follows:

```json
{
  "source": "couchbase|json|csv",
  "type": "timeseries|table",
  "name": "<unique name for this data source>",
  "refresh": "<how often the data should be refreshed (seconds)>"
}
```

Extra fields are required depending on the source and type of data

Couchbase source

```json
{
  "host": "<couchbase host>",
  "username": "<couchbase username>",
  "password": "<couchbase password>",
  "query": "<couchbase query>"
}
```

JSON or CSV source

```json
{
  "file": "<link to file served via http>"
}
```

CSV source

```json
{
  // how the values in the csv are separated
  "delimiter": "<comma, space, tab or custom character>"
}
```

Timeseries type (\_key for JSON and couchbase, \_column for CSV)

```json
{
  // timestamp_key for JSON and couchbase, timestamp_column for CSV
  "timestamp_key|timestamp_column": "<name of key/number of column (0-indexed) that contains the timestamp>",
  // value_key for JSON and couchbase, value_column for CSV
  "value_key|value_column": "<name of key/number of column (0-indexed) that contains the value>"
}
```

Table type

```json
{
  "columns": [
    {
      "text": "<column name to reference in bucket, JSON or CSV>",
      "type": "string|number|time"
    }
  ]
}
```

Each item in the grafana array should be formatted as follows:

```json
{
  "title": "<title of the panel>",
  // panels are arranged using a 24 column grid system
  "grid_position": {
    "h": "<height of the panel (1-24)>",
    "w": "<width of the panel> (1+)",
    "x": "<start position from the left (0-23)>",
    "y": "<start position from the top (0+)>"
  },
  "type": "graph|gauge|stat|table|text"
}
```

Extra fields are required depending on the type of panel

Every type except text

```json
{
  "targets": "<array of target names specified in data above>",
  // passes straight to grafana (optional) - see example for details
  "overrides": {
    "<field name to override>": {
      "<property to override>": "<value to override property with>"
    }
  }
}
```

Graph type (optional)

```json
{
  // if there are multiple lines on a single graph, this determines whether they stack to show a visual total
  "stack": "true|false",
  // by giving different graphs relative times you can show multiple time periods on the same dashboard
  "relative_time": "<grafana relative time statement>"
}
```

Gauge and stat types (optional)

```json
{
  // the final value that shows up in the stat or gauge is calculated based on the set of datapoints
  "calculation": "last|mean|max|min|first"
}
```

Gauge type

```json
{
  // what value is shown as the maximum possible value on the gauge
  "max": "<max value>",
  // coloured areas for different ranges of the gauge
  "thresholds": {
    "mode": "percentage|absolute",
    "steps": [
      {
        "color": "<name or hex code>",
        "value": "<value at which this threshold has been reached or null for any value>"
      }
    ]
  }
}
```

Text type

```json
{
    // a list of links can be created
  "links": [
    {
      "text": "<what the link is displayed as>",
      "link": "<the link itself>"
    }
  ],
  // plain text formatted as markdown
  "text"
}
```

The response you receive will contain the permalink to the created Grafana dashboard. Dashboards have unique names so creating a dashboard with a duplicate name overrides the existing one

Error response:

```json
{
    "error" ""
}
```

If you are only adding data sources (i.e the grafana array is empty):

```json
{
  "result": "data added"
}
```

Creating a dashboard (i.e. panels defined in the grafana array):

```json
{
  "result": "<grafana permalink>"
}
```

# Example

JSON templates can be found in the templates directory.
dynamic_vms.json creates the dashboard found here [here](http://172.23.104.178:3000/d/o2jiYTFMz/dynamic-vms) (VPN required)
