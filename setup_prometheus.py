#!/usr/bin/env python3

import getpass
import requests
import json
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def main():
    cluster_hostname = os.getenv("HS_HOSTNAME") or input("Cluster hostname: ")
    username = os.getenv("HS_USERNAME") or input("Username: ")
    password = os.getenv("HS_PASSWORD") or getpass.getpass("Password: ")
    
    session = requests.Session()

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Origin': f'https://{cluster_hostname}',
        'Referer': f'https://{cluster_hostname}/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
    }
    session.headers.update(headers)

    login_start_url = f"https://{cluster_hostname}/#/auth/login"

    login_url = f"https://{cluster_hostname}/mgmt/v1.2/rest/login"
    login_data = {
        "username": username,
        "password": password,
        "acceptEula": True
    }
    
    try:
        # response = session.get(login_start_url, verify=False)

        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        session.headers.update(headers)
        response = session.post(login_url, data=login_data, verify=False)
        
        if 400 <= response.status_code < 500:
            print(f"Login failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        response.raise_for_status()
                
        nodes_url = f"https://{cluster_hostname}/mgmt/v1.2/rest/nodes"
        session.headers.pop('Content-Type', None)
        
        nodes_response = session.get(nodes_url, verify=False)
        nodes_response.raise_for_status()
        
        nodes_data = nodes_response.json()
        
        # debugging
        # with open("prometheus_targets.json", "w") as f:
        #     json.dump(nodes_data, f, indent=2)

        print("Cluster: {}".format(cluster_hostname))

        # Separate nodes by type
        anvil_nodes = [n for n in nodes_data if n.get("productNodeType") == "ANVIL"]
        dsx_nodes = [n for n in nodes_data if n.get("productNodeType") == "DSX"]
        other_nodes = [n for n in nodes_data if n.get("productNodeType") not in ["ANVIL", "DSX"]]
        
        # Summarize hwComponentStates for ANVIL nodes
        if anvil_nodes:
            print("\n=== ANVIL Nodes ===")
            for node in anvil_nodes:
                hw_states = []
                for component in node.get('hwComponents', []):
                    c_type = component.get('_type', 'UNKNOWN')
                    c_status = component.get('hwComponentState', 'UNKNOWN')
                    if c_status != "UNKNOWN":
                        hw_states.append((c_type, c_status))

                # Summarize hw_states for each node
                ok_count = sum(1 for _, status in hw_states if status == 'OK')
                bad_count = sum(1 for _, status in hw_states if status != 'OK')
                node_hostname = node.get('name', '-')
                node_shortname = node_hostname.split('.')[0] if '.' in node_hostname else node_hostname
                print(f"{node_hostname} ({node_shortname}): {node.get('productNodeType', '-')} - OK:{ok_count} Bad:{bad_count}")
            
        else:
            print("No ANVIL nodes found.")
            exit(1)

        # Summarize hwComponentStates for DSX nodes
        if dsx_nodes:
            print("\n=== DSX Nodes ===")
            for node in dsx_nodes:
                hw_states = []
                for component in node.get('hwComponents', []):
                    c_type = component.get('_type', 'UNKNOWN')
                    c_status = component.get('hwComponentState', 'UNKNOWN')
                    if c_status != "UNKNOWN":
                        hw_states.append((c_type, c_status))

                # Summarize hw_states for each node
                ok_count = sum(1 for _, status in hw_states if status == 'OK')
                bad_count = sum(1 for _, status in hw_states if status != 'OK')
                node_hostname = node.get('name', '-')
                node_shortname = node_hostname.split('.')[0] if '.' in node_hostname else node_hostname
                print(f"{node_hostname} ({node_shortname}): {node.get('productNodeType', '-')} - OK:{ok_count} Bad:{bad_count}")
        else:
            print("No DSX nodes found.")

        if other_nodes:
            print("\n=== Other Nodes ===")
            for node in other_nodes:
                print(f"{node.get('name', '-')}: Please check this system's documentation for Prometheus monitoring targets!")
                
        test_metrics_endpoints(cluster_hostname, anvil_nodes, dsx_nodes)
        
        generate_prometheus_yaml(cluster_hostname, anvil_nodes, dsx_nodes)
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

def test_metrics_endpoints(cluster_hostname, anvil_nodes, dsx_nodes):
    import time
    
    print("\n=== Testing Metrics Endpoints ===")
    
    all_targets = []
    
    # Add cluster targets (ports 9101, 9102, 9103)
    all_targets.append(("cluster", cluster_hostname, 9101))
    all_targets.append(("cluster", cluster_hostname, 9102))
    all_targets.append(("cluster", cluster_hostname, 9103))
    
    # Add ANVIL targets (port 9100)
    for node in sorted(anvil_nodes, key=lambda x: x.get('name', '')):
        hostname = node.get('name', '')
        all_targets.append(("anvil", hostname, 9100))
    
    # Add DSX targets (ports 9100 and 9105)
    for node in sorted(dsx_nodes, key=lambda x: x.get('name', '')):
        hostname = node.get('name', '')
        all_targets.append(("dsx", hostname, 9100))
        all_targets.append(("dsx", hostname, 9105))
    
    # Test each target
    for node_type, hostname, port in all_targets:
        try:
            start_time = time.time()
            url = f"http://{hostname}:{port}/metrics"
            response = requests.get(url, timeout=10, verify=False)
            end_time = time.time()
            
            if response.status_code == 200:
                metrics_count = len([line for line in response.text.split('\n') 
                                   if line.strip() and not line.startswith('#')])
                response_time = (end_time - start_time) * 1000
                print(f"{node_type} {hostname}:{port} - {metrics_count} metrics, {response_time:.1f}ms")
            else:
                print(f"{node_type} {hostname}:{port} - HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"{node_type} {hostname}:{port} - Timeout")
        except requests.exceptions.ConnectionError:
            print(f"{node_type} {hostname}:{port} - Connection refused")
        except Exception as e:
            print(f"{node_type} {hostname}:{port} - Error: {str(e)}")

def generate_prometheus_yaml(cluster_hostname, anvil_nodes, dsx_nodes):
    # Extract cluster shortname (first part before first dot)
    cluster_shortname = cluster_hostname.split('.')[0]
    
    # Embedded prometheus config template
    config_template = f"""global:
  evaluation_interval: 60s
  external_labels:
    monitor: hammerspace_monitor
  scrape_interval: 60s

scrape_configs:
- job_name: prometheus
  static_configs:
  - labels:
      node_type: prometheus
    targets:
    - localhost:9090

### Hammerspace Cluster job
- job_name: cluster
  fallback_scrape_protocol: "PrometheusText0.0.4"
  static_configs:
  - labels:
      cluster: {cluster_shortname}
      cluster_hostname: {cluster_hostname}
      instance: {cluster_shortname}
      node_type: cluster
    targets:
    - {cluster_hostname}:9101
    - {cluster_hostname}:9102
    - {cluster_hostname}:9103

### Hammerspace Anvil job
- job_name: anvil_nodes
  static_configs:"""

    # Add ANVIL nodes
    if anvil_nodes:
        sorted_anvil_nodes = sorted(anvil_nodes, key=lambda x: x.get('name', ''))
        for node in sorted_anvil_nodes:
            node_hostname = node.get('name', '')
            node_shortname = node_hostname.split('.')[0]
            
            config_template += f"""
  - labels:
      cluster: {cluster_shortname}
      cluster_hostname: {cluster_hostname}
      instance: {node_shortname}
      instance_hostname: {node_hostname}
      node_type: anvil
    targets:
    - {node_hostname}:9100"""

    config_template += """

### Hammerspace DSX job
- job_name: dsx_nodes
  fallback_scrape_protocol: "PrometheusText0.0.4"
  static_configs:"""

    # Add DSX nodes
    if dsx_nodes:
        sorted_dsx_nodes = sorted(dsx_nodes, key=lambda x: x.get('name', ''))
        for node in sorted_dsx_nodes:
            node_hostname = node.get('name', '')
            node_shortname = node_hostname.split('.')[0]
            
            config_template += f"""
  - labels:
      cluster: {cluster_shortname}
      cluster_hostname: {cluster_hostname}
      instance: {node_shortname}
      instance_hostname: {node_hostname}
      node_type: dsx
    targets:
    - {node_hostname}:9100
    - {node_hostname}:9105"""

    # Write the final config
    with open('hammerspace_prometheus.yml', 'w') as f:
        f.write(config_template)
    print("")
    print(f"Generated hammerspace_prometheus.yml with for {cluster_shortname} with {len(anvil_nodes)} ANVIL nodes and {len(dsx_nodes)} DSX nodes")
    print("")

if __name__ == "__main__":
    main()