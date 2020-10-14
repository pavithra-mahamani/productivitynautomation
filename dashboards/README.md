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
python dashboard.py admin:password@127.0.0.1:3000
```
