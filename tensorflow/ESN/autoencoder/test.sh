#!/bin/bash
output_dim_arr=(6 12 18 24 30 36)
ae_path_arr=("high" "medium" "low")
for output_dim in ${output_dim_arr[@]}; do
	echo "The output_dim is $output_dim"
    for ae_path in ${ae_path_arr[@]}; do
	    echo "The ae_path is $ae_path"
	    python ae.py --output_dim=$output_dim --ae_path=$ae_path >> 0723.txt
    done
done
