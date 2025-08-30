# Hammerspace Monitoring: Prometheus and Grafana setup and installation

This github repo will walk throught steps to setup and configure Prometheus and Grafana via Docker for Hammerpace monitoring and alerting.

## Requirements

- Python
- Docker
- Hammerspace cluster up and running and Hammerspace login and password
- Network-level access to your Hammerspace cluster on all nodes to ports 9100-9105

## Hammerspace Prometheus endpoint target setup

1. Run `python setup_prometheus.py`. Provide your cluster name (fully qualified domain name) as well as username and password. You can also configure these parameters as environment variables: HS_HOSTNAME, HS_USERNAME, HS_PASSWORD
2. Check the output of the `python setup_prometheus.py` to confirm everything ran smoothly.
3. If everything worked, you will now have the hammerspace_prometheus.yml ready to go.

## Start up Prometheus and Grafana via docker

1. Check the docker-compose.yml to confirm it's configure to work in you environment. Change the default Grafana admin user and password if needed (GF_SECURITY_ADMIN_USER, GF_SECURITY_ADMIN_PASSWORD).
2. Run `docker-compose up -d`
3. Check logs to confirm things are up and running: 
    - `docker logs -n 100 prometheus` - Don't worry if you see "Error on ingesting samples with different value but same timestamp". Those are minor issues that will get resolved in future Hammerspace releases.
    - `docker logs -n 100 grafana` - Look for something like "inserting datasource from configuration"
4. After a minute or two, confirm everything is "scraping" correctly by going here: http://localhost:9090/targets
5. Finally, go to the Grafana UI and confirm you can see metrics rolling in here: http://localhost:3000/a/grafana-metricsdrilldown-app/drilldown?search_txt=hammerspace

