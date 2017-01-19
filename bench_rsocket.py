#!/usr/bin/env python
# encoding: utf-8

import argparse
import paramiko
import subprocess
import sys
import time

class Server(object):
	def __init__(self, host, user, password, port, with_rsocket, clients):
		self.host = host
		self.user = user
		self.password = password
		self.port = port
		self.with_rsocket = with_rsocket
		self.clients = clients

	def init(self):
		client = paramiko.SSHClient()
		client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		client.connect(hostname=self.host, username=self.user,
			password=self.password, port=self.port)
		self.client = client

		self.__exec_command("pg_bin/bin/initdb -D bench_data")

		# Set configuration
		if self.with_rsocket:
			self.__exec_command("""echo "listen_addresses = ''" >> bench_data/postgresql.conf""")
			self.__exec_command(
				"""echo "listen_rdma_addresses = '{0}'" >> bench_data/postgresql.conf""".format(self.host))
		self.__exec_command("""echo "shared_buffers = 8GB" >> bench_data/postgresql.conf""")
		self.__exec_command("""echo "fsync = off" >> bench_data/postgresql.conf""")
		self.__exec_command("""echo "synchronous_commit = off" >> bench_data/postgresql.conf""")
		if self.clients > 100:
			self.__exec_command("""echo "max_connections = {0}" >> bench_data/postgresql.conf""".format(self.clients))		

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
			print stderr.read()
			sys.exit("Command '{0}' failed with code: {1}".format(cmd,
				stderr.channel.recv_exit_status()))

class Shell(object):
	def __init__(self, cmd, wait_time = 0):
		self.cmd = cmd
		self.run()

	def run(self):
		p = subprocess.Popen(self.cmd, shell=True,
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
		while p.poll() is None:
			time.sleep(1)
		if p.returncode != 0:
			out, err = p.communicate()
			print err
			sys.exit("Command '{0}' failed with code: {1}".format(
				self.cmd, p.returncode))


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
	parser.add_argument("--with-rsocket",
		help="Enable rsocket",
		action="store_true",
		default=False,
		dest="with_rsocket")

	args = parser.parse_args()

	serv = Server(args.host, args.user, args.password, args.port,
		args.with_rsocket, args.clients)
	serv.init()
	serv.run()
	serv.stop()
