# raritan-pdu-exporter
Get power metrics from Raritan PDUs

Uses lots of ideas from blackbox exporter, and here:
<https://github.com/yrro/nexsan-exporter>

## Install

You can install this in a venv like so:

    python3 -m venv .venv
    . .venv/bin/activate
    pip install -U pip
    pip install -r requirements.txt

To run the exporter do and try it, do:

    ./exporter.py &
    curl "http://localhost:8042/probe?target=10.42.1.1\&user=admin\&pass=mysecret"

## Prometheus configuration

Something like the following:

    scrape_configs:
     - job_name: raritan
       metrics_path: /probe
       static_configs:
        - targets:
            - 10.42.2.1
            - 10.42.2.2
       relabel_configs:
        - source_labels: [__address__]
          target_label: __param_target
        - source_labels: [__param_target]
          target_label: instance
        - target_label: __address__
          replacement: exporter-host:8042
