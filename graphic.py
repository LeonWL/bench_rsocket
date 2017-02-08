#!/usr/bin/env python
# encoding: utf-8

import argparse
import matplotlib.pyplot as plt

def read_csv(csv_file):
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
			# Latency
			y.append(float(s[1]))

	return x, y

def make_graphic(rsocket_csv, socket_csv):
	rsocket_x, rsocket_y = read_csv(rsocket_csv)
	socket_x, socket_y = read_csv(socket_csv)

	f, ax = plt.subplots()
	ax.plot(rsocket_x, rsocket_y, color="blue", marker="s", label="rsocket")
	ax.plot(socket_x, socket_y, color="red", marker="s", label="socket")

	ax.set_title("pgbench, scale factor 100, time 30 minute\nshared_buffers = 8GB")
	ax.set_xlabel("Number of clients")
	ax.set_ylabel("TPS")
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
	parser.add_argument("-s", "--socket-csv",
		type=str,
		help="socket benchmark result",
		required=True,
		dest="socket_csv")

	args = parser.parse_args()
	make_graphic(args.rsocket_csv, args.socket_csv)
