#!/usr/bin/env python
# encoding: utf-8

import argparse
import csv
import datetime
import paramiko
import sys

class PrimaryServer(object):
	def __init__(self, host, scale, with_rsocket):
		self.host = host
		self.scale = scale
		self.with_rsocket = with_rsocket

	def init(self):
		Shell("pg_bin/bin/initdb -D repl_bench_data")

		# Set configuration
		with open("repl_bench_data/postgresql.auto.conf") as f:
			if self.with_rsocket:
				f.write("listen_addresses = ''")
				f.write(
					"listen_rdma_addresses = '{0}'".format(self.host))

			f.write("shared_buffers = 8GB")
			f.write("work_mem = 50MB")
			f.write("maintenance_work_mem = 2GB")

			f.write("fsync = off")
			f.write("synchronous_commit = remote_write")

			f.write("wal_level = hot_standby")
			f.write("max_wal_senders = 2")
			f.write("synchronous_standby_names = '*'")
			f.write("hot_standby = on")

	def run(self):
		Shell("pg_bin/bin/initdb -w start -D repl_bench_data")
		Shell("pg_bin/bin/createdb pgbench")
		Shell("pg_bin/bin/pgbench -s {0} -i pgbench".format(self.scale))

	def stop(self):
		Shell("pg_bin/bin/initdb -w stop -D repl_bench_data")
		Shell("rm -rf bench_data")

class StandbyServer(object):
	def __init__(self, primary_host, standby_host, user, password, port,
		with_rsocket):
		self.primary_host = primary_host
		self.standby_host = standby_host
		self.user = user
		self.password = password
		self.port = port
		self.with_rsocket = with_rsocket

	def init(self):
		client = paramiko.SSHClient()
		client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		client.connect(hostname=self.standby_host, username=self.user,
			password=self.password, port=self.port)
		self.client = client

		self.__exec_command(("pg_bin/bin/pg_basebackup -D repl_bench_data "
			"-x -R -h {0} {2}").format(self.primary_host,
			"--with-rsocket" if self.with_rsocket else ""))

		self.__exec_command("""echo "listen_addresses = '*'" >> bench_data/postgresql.auto.conf""")
		self.__exec_command("""echo "listen_rdma_addresses = ''" >> bench_data/postgresql.auto.conf""")

	def run(self):
		self.__exec_command("pg_bin/bin/pg_ctl -w start -D repl_bench_data")
		self.__exec_command("pg_bin/bin/createdb pgbench")

	def stop(self):
		self.__exec_command("pg_bin/bin/pg_ctl -w stop -D repl_bench_data")
		self.__exec_command("rm -rf repl_bench_data")
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
		while p.poll() is None:
			time.sleep(1)
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
	def __init__(self, primary_server, standby_server, clients, run_time):
		self.primary_server = primary_server
		self.standby_server = standby_server
		self.clients = clients
		self.run_time = run_time

	def run(self):
		print("Initialize primary server...")
		self.primary_server.init()
		print("Run primary database server...")
		self.primary_server.run()

		print("Initialize standby server...")
		self.standby_server.init()
		print("Run standby database server...")
		self.standby_server.run()

		print("\n")

		filename = "{0}_{1}_clients_{2}.csv".format(
			"rsocket" if self.primary_server.with_rsocket else "socket"
			self.clients, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))

		w = Writer(filename)

		for i in range(0, self.clients):
			print("Run pgbench for {0} clients...".format(i + 1))

			out = Shell("pg_bin/bin/pgbench {0} -c {1} -T {2} -v pgbench".format(
				"--with-rsocket" if self.primary_server.with_rsocket else "",
				i + 1, self.run_time))
			res = Result(out.stdout)

			w.add_value(i + 1, res.tps, res.trans, res.avg_latency)
			print("Test result: tps={0} trans={1} avg_latency={2}\n".format(
				res.tps, res.trans, res.avg_latency))

		w.close()

		print("Stop standby database server. Remove data directory...")
		self.standby_server.stop()

		print("Stop primary database server. Remove data directory...")
		self.primary_server.stop()

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="rsocket benchmark tool",
		add_help=False)

	parser.add_argument("-?", "--help",
		action="help",
		help="Show this help message and exit")
	parser.add_argument("--primary",
		type=str,
		help="Primary database server''s host name",
		required=True,
		dest="primary_host")
	parser.add_argument("--standby",
		type=str,
		help="Standby database server''s host name",
		required=True,
		dest="standby_host")
	parser.add_argument("-u", "--user",
		type=str,
		help="User to connect through ssh",
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

	args = parser.parse_args()

	# Run rsocket test
	prim_serv = PrimaryServer(args.primary_host, args.scale, True)
	standby_serv = StandbyServer(args.primary_host, args.standby_host,
		args.user, args.password, args.port, True)
	test = Test(prim_serv, standby_serv, args.clients, args.time)
	test.run()

	# Run socket test
	prim_serv = PrimaryServer(args.primary_host, args.scale, False)
	standby_serv = StandbyServer(args.primary_host, args.standby_host,
		args.user, args.password, args.port, False)
	test = Test(prim_serv, standby_serv, args.clients, args.time)
	test.run()

	print("Finished")