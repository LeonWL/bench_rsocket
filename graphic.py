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

def make_graphic(rsocket_csv, socket_csv, vma1_csv, vma2_csv, mode):
	rsocket_x, rsocket_y = read_csv(rsocket_csv, mode)
	socket_x, socket_y = read_csv(socket_csv, mode)

	if (vma1_csv is not None):
		vma1_x, vma1_y = read_csv(vma1_csv, mode)
	else:
		vma1_x, vma1_y = None

	if (vma2_csv is not None):
		vma2_x, vma2_y = read_csv(vma2_csv, mode)
	else:
		vma2_x, vma2_y = None

	f, ax = plt.subplots()
	ax.plot(rsocket_x, rsocket_y, color="black", marker="s", label="rsocket")
	ax.plot(socket_x, socket_y, color="red", marker="s", label="socket")
	if (vma1_csv is not None):
		ax.plot(vma1_x, vma1_y, color="green", marker="s", label="vma1")
	if (vma2_csv is not None):
		ax.plot(vma2_x, vma2_y, color="blue", marker="s", label="vma2")
	ax.set_ylim(ymin=0)

	ax.set_title("pgbench, -s 30 -c 8 -j 8 -T 20")
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
	parser.add_argument("-s", "--socket-csv",
		type=str,
		help="socket benchmark result",
		required=True,
		dest="socket_csv")
	parser.add_argument("--vma1-csv",
		type=str,
		help="vma benchmark result",
		required=False,
		dest="vma1_csv")
	parser.add_argument("--vma2-csv",
		type=str,
		help="vma benchmark result using VMA_SELECT_POLL environment variable",
		required=False,
		dest="vma2_csv")
	parser.add_argument("-m", "--mode",
		type=str,
		help="TPS or Latency visualization",
		default="tps",
		choices=['tps', 'latency'],
		dest="mode")

	args = parser.parse_args()
	make_graphic(args.rsocket_csv, args.socket_csv, args.vma1_csv, args.vma2_csv, args.mode)
