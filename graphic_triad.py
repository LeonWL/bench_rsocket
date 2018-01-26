#!/usr/bin/env python
# encoding: utf-8

import argparse
import matplotlib.pyplot as plt

def read_csv(csv_file, mode):
	x = []
	y = []
	i = 0

	with open(csv_file, "rb") as f:
		for row in f:
			# Skip header row
			if i == 0:
				i += 1
				continue

			s = row.split(b",", 4)

			# Clients
			x.append(int(s[0]))
			# TPS
			if mode == "tps":
				y.append(float(s[1]))
			# Latency
			else:
				y.append(float(s[3]))

	return x, y

def make_graphic(rsocket_csv, ucx_csv, socket_csv, mode):
	rsocket_x, rsocket_y = read_csv(rsocket_csv, mode)
	ucx_x, ucx_y = read_csv(ucx_csv, mode)

	if (socket_csv is not None):
		socket_x, socket_y = read_csv(socket_csv, mode)
	else:
		socket_x, socket_y = None, None

	f, ax = plt.subplots()
	ax.plot(rsocket_x, rsocket_y, color="black", marker="s", label="rsocket")
	ax.plot(ucx_x, ucx_y, color="green", marker="s", label="ucx")
	if (socket_csv is not None):
		ax.plot(socket_x, socket_y, color="red", marker="s", label="socket")
	ax.set_ylim(ymin=0)

	ax.set_title("pgbench, -s 30 -c 12 -j 12 -T 20")
	ax.set_xlabel("Number of clients")
	if mode == "tps":
		ax.set_ylabel("TPS")
	else:
		ax.set_ylabel("Latency, ms")
	# Lower left corner
	ax.legend(loc=4)
	ax.grid(True)

	plt.savefig("bench_rsocket.svg")

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Graphics creator")
	parser.add_argument("-r", "--rsocket-csv",
		type=str,
		help="rsocket benchmark result",
		required=True,
		dest="rsocket_csv")
	parser.add_argument("-u", "--ucx-csv",
		type=str,
		help="ucx benchmark result",
		required=True,
		dest="ucx_csv")
	parser.add_argument("-s", "--socket-csv",
		type=str,
		help="socket benchmark result",
		required=False,
		dest="socket_csv")
	parser.add_argument("-m", "--mode",
		type=str,
		help="TPS or Latency visualization",
		default="tps",
		choices=['tps', 'latency'],
		dest="mode")

	args = parser.parse_args()
	make_graphic(args.rsocket_csv, args.ucx_csv, args.socket_csv, args.mode)
