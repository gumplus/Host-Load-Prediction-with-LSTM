#!/bin/bash

interval_arr=(8 7 6 5 4 3 2 1)
for interval in ${interval_arr[@]}; do
	echo "The interval is $interval"
	python lstm_msse_main.py --interval=$interval >> 1012.txt
done
