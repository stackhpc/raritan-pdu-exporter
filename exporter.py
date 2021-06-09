#!/bin/python3

import io
import time
import threading
import urllib.parse

from wsgiref.simple_server import make_server, WSGIRequestHandler
import wsgiref.util

import prometheus_client
from prometheus_client import core as prometheus

from raritan import rpc
from raritan.rpc import pdumodel

# Inspired by
# https://github.com/yrro/nexsan-exporter/blob/master/nexsan_exporter/exporter.py


def wsgi_app(environ, start_response):
    name = wsgiref.util.shift_path_info(environ)
    if name == '':
        return front(environ, start_response)
    if name == 'probe':
        return probe(environ, start_response)
    elif name == 'metrics':
        return prometheus_app(environ, start_response)
    return not_found(environ, start_response)


def front(environ, start_response):
    with io.BytesIO() as page:
        page.write(
            b'<html>'
                b'<head>'
                    b'<title>PDU exporter</title>'
                    b'<style>'
                        b'form { display: grid; grid-template-columns: 175px 175px; grid-gap: 16px; }'
                        b'label { grid-column: 1 / 2; text-align: right; }'
                        b'input, button { grid-column: 2 / 3; }'
                    b'</style>'
                b'</head>'
                b'<body>'
                    b'<h1>PDU Exporter</h1>'
                    b'<p>Use this form to probe an array:'
                    b'<form method="get" action="/probe">'
                        b'<label for="target">Probe address:</label>'
                        b'<input type="text" id="target" name="target" required placeholder="10.45.1.1">'
                        b'<label for="user">User:</label>'
                        b'<input type="text" id="user" name="user" required placeholder="admin">'
                        b'<label for="pass">Password:</label>'
                        b'<input type="password" required id="pass" name="pass">'
                        b'<button type="submit">Probe</button>'
                    b'</form>'
                    b'<hr>'
                    b'<p><a href="/metrics">Metrics</a>'
                b'</body>'
            b'</html>'
        )

        start_response('200 OK', [('Content-Type', 'text/html')])
        return [page.getvalue()]


def probe(environ, start_response):
    qs = urllib.parse.parse_qs(environ['QUERY_STRING'])

    reg = prometheus_client.CollectorRegistry()
    reg.register(RaritanPDUCollector(target=qs['target'][0], user=qs['user'][0], password=qs['pass'][0]))
    body = prometheus_client.generate_latest(reg)

    start_response('200 OK', [('Content-Type', prometheus_client.CONTENT_TYPE_LATEST)])
    return [body]


prometheus_app = prometheus_client.make_wsgi_app()


def not_found(environ, start_response):
    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b'Not Found\r\n']


def get_agent(ip, user, pw):
    return rpc.Agent("https", ip, user, pw, disable_certificate_verification=True)
    # TODO?? return rpc.Agent("https", ip, user, pw)


class RaritanPDUCollector(object):
    def __init__(self, target, user, password):
        self.target = target
        self.user = user
        self.password = password

    def collect(self):
        agent = get_agent(self.target, self.user, self.password)
        pdu = pdumodel.Pdu("/model/pdu/0", agent)

        #pdu_sensors = pdu.getSensors()
        #pdu_power = prometheus.GaugeMetricFamily("PDUActivePower", 'Outlet power in W',
        #                                         labels=['pdu'])
        #pdu_energy = prometheus.GaugeMetricFamily("PDUActiveEnergy", 'Outlet energy in J',
        #                                          labels=['pdu'])
        #pdu_power.add_metric([self.target], pdu_sensors.activePower.getReading().value)
        #pdu_energy.add_metric([self.target], pdu_sensors.activeEnergy.getReading().value)
        #yield pdu_power
        #yield pdu_energy

        outlet_power = prometheus.GaugeMetricFamily("OutletActivePower", 'Outlet power in W',
                                                    labels=['pdu', 'outlet'])
        outlet_energy = prometheus.GaugeMetricFamily("OutletActiveEnergy", 'Outlet energy in J',
                                                     labels=['pdu', 'outlet'])

        outlets = pdu.getOutlets()
        for outlet in outlets:
            outlet_sensors = outlet.getSensors()
            outlet_metadata = outlet.getMetaData()
            outlet_power.add_metric([self.target, outlet_metadata.label], outlet_sensors.activePower.getReading().value)
            outlet_energy.add_metric([self.target, outlet_metadata.label], outlet_sensors.activeEnergy.getReading().value)

        yield outlet_power
        yield outlet_energy

        inlet_power = prometheus.GaugeMetricFamily("InletActivePower", 'Inlet power in W',
                                                   labels=['pdu', 'inlet'])
        inlets = pdu.getInlets()
        for inlet in inlets:
            inlet_sensors = inlet.getSensors()
            inlet_metadata = inlet.getMetaData()
            inlet_power.add_metric([self.target, inlet_metadata.label], inlet_sensors.activePower.getReading().value)

        yield inlet_power


class _SilentHandler(WSGIRequestHandler):
    """WSGI handler that does not log requests."""

    def log_message(self, format, *args):
        """Log nothing."""


def start_wsgi_server(port, addr=''):
    """Starts a WSGI server for prometheus metrics as a daemon thread."""
    app = wsgi_app
    httpd = make_server(addr, port, app, prometheus_client.exposition.ThreadingWSGIServer, handler_class=_SilentHandler)
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()


if __name__ == '__main__':
    start_wsgi_server(8042)
    while True:
        time.sleep(1)
