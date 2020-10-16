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

This example JSON generates the entire dashboard shown [here](http://172.23.104.178:3000/d/o2jiYTFMz/dynamic-vms) (VPN required)

```json
{
  "dashboard_title": "Dynamic VMs",
  "data": [
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT MAX(created_time*1000) as timestamp, (SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_TRUNC_MILLIS(created_time*1000, 'day') order by timestamp asc",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "compute_hours",
      "name": "compute_hours_daily"
    },
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT MAX(created_time*1000) as timestamp, count(*) AS count FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_TRUNC_MILLIS(created_time*1000, 'day') order by timestamp asc",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "count",
      "name": "vms_created_daily"
    },
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT (SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours, MAX(created_time)*1000 AS timestamp FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_PART_MILLIS(created_time*1000, 'iso_week') ORDER BY timestamp ASC",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "compute_hours",
      "name": "compute_hours_weekly"
    },
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT COUNT(*) as count, MAX(created_time)*1000 AS timestamp FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_PART_MILLIS(created_time*1000, 'iso_week') AS week ORDER BY timestamp ASC",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "count",
      "name": "vms_created_weekly"
    },
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT MAX(created_time*1000) as timestamp, (SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_TRUNC_MILLIS(created_time*1000, 'month') order by timestamp asc",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "compute_hours",
      "name": "compute_hours_monthly"
    },
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT MAX(created_time*1000) as timestamp, count(*) AS count FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_TRUNC_MILLIS(created_time*1000, 'month') order by timestamp asc",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "count",
      "name": "vms_created_monthly"
    },
    {
      "source": "couchbase",
      "type": "table",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "select timestamp, (SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours, count(*) as vms_created FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_TRUNC_MILLIS(created_time*1000, 'day') as timestamp order by timestamp desc",
      "refresh": 60,
      "columns": [
        {
          "text": "timestamp",
          "type": "time"
        },
        {
          "text": "compute_hours",
          "type": "number"
        },
        {
          "text": "vms_created",
          "type": "number"
        }
      ],
      "name": "daily_stats"
    },
    {
      "source": "couchbase",
      "type": "table",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT MAX(created_time*1000) as timestamp, (SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours, count(*) as vms_created FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_PART_MILLIS(created_time*1000, 'iso_week') order by timestamp desc",
      "refresh": 60,
      "columns": [
        {
          "text": "timestamp",
          "type": "time"
        },
        {
          "text": "compute_hours",
          "type": "number"
        },
        {
          "text": "vms_created",
          "type": "number"
        }
      ],
      "name": "weekly_stats"
    },
    {
      "source": "couchbase",
      "type": "table",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "select timestamp, (SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours, count(*) as vms_created FROM `QE-dynserver-pool` WHERE ipaddr != '' GROUP BY DATE_TRUNC_MILLIS(created_time*1000, 'month') as timestamp order by timestamp desc",
      "refresh": 60,
      "columns": [
        {
          "text": "timestamp",
          "type": "time"
        },
        {
          "text": "compute_hours",
          "type": "number"
        },
        {
          "text": "vms_created",
          "type": "number"
        }
      ],
      "name": "monthly_stats"
    },
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT os,timestamp,(SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours FROM `QE-dynserver-pool` WHERE ipaddr != '' AND live_duration_secs IS NOT NULL AND create_duration_secs IS NOT NULL AND delete_duration_secs IS NOT NULL GROUP BY os, DATE_TRUNC_MILLIS(created_time*1000,'day') AS timestamp ORDER BY timestamp ASC",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "compute_hours",
      "name": "compute_hours_by_os",
      "group_by": "os"
    },
    {
      "source": "couchbase",
      "type": "timeseries",
      "host": "172.23.104.180",
      "username": "Administrator",
      "password": "password",
      "query": "SELECT origin,timestamp,(SUM(live_duration_secs)+SUM(create_duration_secs)+SUM(delete_duration_secs))/3600 AS compute_hours FROM `QE-dynserver-pool` WHERE ipaddr != '' AND live_duration_secs IS NOT NULL AND create_duration_secs IS NOT NULL AND delete_duration_secs IS NOT NULL GROUP BY origin, DATE_TRUNC_MILLIS(created_time*1000,'day') AS timestamp ORDER BY timestamp ASC",
      "refresh": 60,
      "timestamp_key": "timestamp",
      "value_key": "compute_hours",
      "name": "compute_hours_by_xen_host",
      "group_by": "origin"
    }
  ],
  "grafana": [
    {
      "title": "Links",
      "grid_position": {
        "h": 4,
        "w": 24,
        "x": 0,
        "y": 0
      },
      "type": "text",
      "links": [
        {
          "text": "Visit the wiki to learn how to create your own dashboard",
          "link": "https://hub.internal.couchbase.com/confluence/display/QA/Dynamic+VMs+Usage"
        }
      ]
    },
    {
      "title": "Daily",
      "grid_position": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 4
      },
      "type": "graph",
      "targets": ["compute_hours_daily", "vms_created_daily"],
      "relative_time": "now-7d"
    },
    {
      "title": "Weekly",
      "grid_position": {
        "h": 8,
        "w": 8,
        "x": 8,
        "y": 4
      },
      "type": "graph",
      "targets": ["compute_hours_weekly", "vms_created_weekly"],
      "relative_time": "now-4w",
      "overrides": {
        "vms_created_weekly": {
          "displayName": "VMs Created"
        },
        "compute_hours_weekly": {
          "displayName": "Compute Hours"
        }
      }
    },
    {
      "title": "Monthly",
      "grid_position": {
        "h": 8,
        "w": 8,
        "x": 16,
        "y": 4
      },
      "type": "graph",
      "targets": ["compute_hours_monthly", "vms_created_monthly"],
      "relative_time": "now-12M",
      "overrides": {
        "vms_created_monthly": {
          "displayName": "VMs Created"
        },
        "compute_hours_monthly": {
          "displayName": "Compute Hours"
        }
      }
    },
    {
      "title": "Compute Hours Today",
      "grid_position": {
        "h": 4,
        "w": 4,
        "x": 0,
        "y": 12
      },
      "type": "gauge",
      "targets": ["compute_hours_daily"],
      "thresholds": {
        "mode": "percentage",
        "steps": [
          {
            "color": "red",
            "value": null
          },
          {
            "color": "#EAB839",
            "value": 50
          },
          {
            "color": "green",
            "value": 75
          }
        ]
      },
      "max": 960,
      "calculation": "last"
    },
    {
      "title": "VMs Created Today",
      "grid_position": {
        "h": 4,
        "w": 4,
        "x": 4,
        "y": 12
      },
      "type": "stat",
      "targets": ["vms_created_daily"],
      "calculation": "last"
    },
    {
      "title": "Daily",
      "grid_position": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 16
      },
      "type": "table",
      "targets": ["daily_stats"],
      "overrides": {
        "vms_created": {
          "displayName": "VMs Created"
        },
        "timestamp": {
          "displayName": "Timestamp"
        },
        "compute_hours": {
          "custom.displayMode": "basic",
          "displayName": "Compute Hours",
          "thresholds": {
            "mode": "percentage",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "#EAB839",
                "value": 50
              },
              {
                "color": "green",
                "value": 75
              }
            ]
          },
          "max": 960
        }
      }
    },
    {
      "title": "Compute Hours This Week",
      "grid_position": {
        "h": 4,
        "w": 4,
        "x": 8,
        "y": 12
      },
      "type": "gauge",
      "targets": ["compute_hours_weekly"],
      "thresholds": {
        "mode": "percentage",
        "steps": [
          {
            "color": "red",
            "value": null
          },
          {
            "color": "#EAB839",
            "value": 50
          },
          {
            "color": "green",
            "value": 75
          }
        ]
      },
      "max": 6720,
      "calculation": "last"
    },
    {
      "title": "VMs Created This Week",
      "grid_position": {
        "h": 4,
        "w": 4,
        "x": 12,
        "y": 12
      },
      "type": "stat",
      "targets": ["vms_created_weekly"],
      "calculation": "last"
    },
    {
      "title": "Weekly",
      "grid_position": {
        "h": 8,
        "w": 8,
        "x": 8,
        "y": 16
      },
      "type": "table",
      "targets": ["weekly_stats"],
      "overrides": {
        "vms_created": {
          "displayName": "VMs Created"
        },
        "timestamp": {
          "displayName": "Timestamp"
        },
        "compute_hours": {
          "custom.displayMode": "basic",
          "displayName": "Compute Hours",
          "thresholds": {
            "mode": "percentage",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "#EAB839",
                "value": 50
              },
              {
                "color": "green",
                "value": 75
              }
            ]
          },
          "max": 6720
        }
      }
    },
    {
      "title": "Compute Hours This Month",
      "grid_position": {
        "h": 4,
        "w": 4,
        "x": 16,
        "y": 12
      },
      "type": "gauge",
      "targets": ["compute_hours_monthly"],
      "thresholds": {
        "mode": "percentage",
        "steps": [
          {
            "color": "red",
            "value": null
          },
          {
            "color": "#EAB839",
            "value": 50
          },
          {
            "color": "green",
            "value": 75
          }
        ]
      },
      "max": 28800,
      "calculation": "last"
    },
    {
      "title": "VMs Created This Month",
      "grid_position": {
        "h": 4,
        "w": 4,
        "x": 20,
        "y": 12
      },
      "type": "stat",
      "targets": ["vms_created_monthly"],
      "calculation": "last"
    },
    {
      "title": "Monthly",
      "grid_position": {
        "h": 8,
        "w": 8,
        "x": 16,
        "y": 16
      },
      "type": "table",
      "targets": ["monthly_stats"],
      "overrides": {
        "vms_created": {
          "displayName": "VMs Created"
        },
        "timestamp": {
          "displayName": "Timestamp"
        },
        "compute_hours": {
          "custom.displayMode": "basic",
          "displayName": "Compute Hours",
          "thresholds": {
            "mode": "percentage",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "#EAB839",
                "value": 50
              },
              {
                "color": "green",
                "value": 75
              }
            ]
          },
          "max": 28800
        }
      }
    },
    {
      "title": "Daily Compute Hours by OS",
      "grid_position": {
        "h": 12,
        "w": 12,
        "x": 0,
        "y": 24
      },
      "type": "graph",
      "targets": ["compute_hours_by_os"],
      "relative_time": "now-6M"
    },
    {
      "title": "Daily Compute Hours by Xen Host",
      "grid_position": {
        "h": 12,
        "w": 12,
        "x": 12,
        "y": 24
      },
      "type": "graph",
      "targets": ["compute_hours_by_xen_host"],
      "relative_time": "now-6M",
      "stack": true
    }
  ]
}
```
