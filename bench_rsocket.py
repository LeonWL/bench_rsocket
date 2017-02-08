#!/usr/bin/env python
# encoding: utf-8

import argparse
import csv
import datetime
import os
import paramiko
import re
import subprocess
import sys
import time

class Server(object):
	def __init__(self, host, user, password, port, with_rsocket):
		self.host = host
		self.user = user
		self.password = password
		self.port = port
		self.with_rsocket = with_rsocket

	def init(self):
		client = paramiko.SSHClient()
		client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		client.connect(hostname=self.host, username=self.user,
			password=self.password, port=self.port)
		self.client = client

		self.__exec_command("pg_bin/bin/initdb -D bench_data")

		# Set configuration
		if self.with_rsocket:
			self.__exec_command("""echo "listen_addresses = ''" >> bench_data/postgresql.auto.conf""")
			self.__exec_command(
				"""echo "listen_rdma_addresses = '{0}'" >> bench_data/postgresql.auto.conf""".format(self.host))

		self.__exec_command("""echo "shared_buffers = 8GB" >> bench_data/postgresql.auto.conf""")
		self.__exec_command("""echo "work_mem = 50MB" >> bench_data/postgresql.auto.conf""")
		self.__exec_command("""echo "maintenance_work_mem = 2GB" >> bench_data/postgresql.auto.conf""")
		self.__exec_command("""echo "max_wal_size = 8GB" >> bench_data/postgresql.auto.conf""")

		self.__exec_command("""echo "fsync = off" >> bench_data/postgresql.auto.conf""")
		self.__exec_command("""echo "synchronous_commit = off" >> bench_data/postgresql.auto.conf""")

	def run(self):
		self.__exec_command("pg_bin/bin/pg_ctl -w start -D bench_data")
		self.__exec_command("pg_bin/bin/createdb pgbench")

	def stop(self):
		self.__exec_command("pg_bin/bin/pg_ctl -w stop -D bench_data")
		self.__exec_command("rm -rf bench_data")
		self.client.close()

	def __exec_command(self, cmd):
		stdin, stdout, stderr = self.client.exec_command(cmd)
		if stderr.channel.recv_exit_status() != 0:
			print(stderr.read())
			sys.exit("Command '{0}' failed with code: {1}".format(cmd,
				stderr.channel.recv_exit_status()))

class Shell(object):
	def __init__(self, cmd, wait_time = 0):
		self.cmd = cmd
		self.stdout = None
		self.run()

	def run(self):
		p = subprocess.Popen(self.cmd, shell=True,
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
		p.wait()
		if p.returncode != 0:
			out, err = p.communicate()
			print(err)
			sys.exit("Command '{0}' failed with code: {1}".format(
				self.cmd, p.returncode))
		self.stdout = "".join(p.stdout.readlines())

class Result(object):
	def __init__(self, out):
		try:
			self.out = out
			m = re.search('tps = (\d+)(,|\.)(.+)including connections establishing(.+)', self.out)
			self.tps = int(m.group(1))
			m = re.search('number of transactions actually processed\: (\d+)', self.out)
			self.trans = int(m.group(1))
			m = re.search('latency average = (\d+)\.(\d+) ms', self.out)
			self.avg_latency = float(m.group(1)+"."+m.group(2))
		except AttributeError:
			sys.exit("Can't parse stdout:\n{0}".format(self.out))

class Writer(object):
	def __init__(self, filename):
		self.f = open(filename, "wb")
		fieldnames = ["clients", "tps", "trans", "avg_latency"]
		self.writer = csv.DictWriter(self.f, fieldnames)
		self.writer.writeheader()

	def add_value(self, clients, tps, trans, avg_latency):
		self.writer.writerow({"clients": clients, "tps": tps, "trans": trans,
			"avg_latency": avg_latency})

	def close(self):
		self.f.close()

class Test(object):
	def __init__(self, server, scale, clients, run_time, select_only):
		self.server = server
		self.scale = scale
		self.clients = clients
		self.run_time = run_time
		self.select_only = select_only

	def run(self):
		with_rsocket = "--with-rsocket" if self.server.with_rsocket else ""
		select_only = "--select-only" if self.select_only else ""

		filename = "{0}_{1}_clients_{2}.csv".format(
			"rsocket" if self.server.with_rsocket else "socket",
			self.clients, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))

		w = Writer(filename)

		for i in range(0, self.clients):
			if i != 0:
				print("\n")

			print("Initialize data directory...")
			self.server.init()
			print("Run database server...")
			self.server.run()

			print("Initialize pgbench database...")
			Shell("pg_bin/bin/pgbench -h {0} {1} -s {2} -i pgbench".format(
				self.server.host, with_rsocket, self.scale))

			print("Run pgbench for {0} clients...".format(i + 1))

			out = Shell("pg_bin/bin/pgbench -h {0} {1} {2} -c {3} -T {4} -v pgbench".format(
				self.server.host, with_rsocket, select_only, i + 1, self.run_time))
			res = Result(out.stdout)

			w.add_value(i + 1, res.tps, res.trans, res.avg_latency)
			print("Test result: tps={0} trans={1} avg_latency={2}".format(
				res.tps, res.trans, res.avg_latency))

			print("Stop database server. Remove data directory...")
			self.server.stop()

		w.close()

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="rsocket benchmark tool",
		add_help=False)
	parser.add_argument("-?", "--help",
		action="help",
		help="Show this help message and exit")
	parser.add_argument("-h", "--host",
		type=str,
		help="Database server''s host name",
		required=True,
		dest="host")
	parser.add_argument("-u", "--user",
		type=str,
		help="User to connect through ssh and libpq",
		required=True,
		dest="user")
	parser.add_argument("--password",
		type=str,
		help="Password to connect through ssh",
		required=True,
		dest="password")
	parser.add_argument("-p", "--port",
		type=int,
		help="Ssh port",
		default=22,
		dest="port")
	parser.add_argument("-s", "--scale",
		type=int,
		help="Scale of tables",
		default=100,
		dest="scale")
	parser.add_argument("-t", "--time",
		type=int,
		help="Time for tests",
		default=120,
		dest="time")
	parser.add_argument("-c", "--clients",
		type=int,
		help="Maximum number of clients",
		default=100,
		dest="clients")
	parser.add_argument("-S", "--select-only",
		help="Run select-only script",
		action="store_true",
		default=False,
		dest="select_only")

	args = parser.parse_args()

	# Run rsocket test
	serv = Server(args.host, args.user, args.password, args.port, True)
	test = Test(serv, args.scale, args.clients, args.time, args.select_only)
	test.run()

	# Run socket test
	serv = Server(args.host, args.user, args.password, args.port, False)
	test = Test(serv, args.scale, args.clients, args.time, args.select_only)
	test.run()

	print("Finished")
