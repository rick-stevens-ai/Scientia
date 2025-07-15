#!/bin/bash

PROMPT="I want you to try to find a plausible function for this gene in MtB genome.  Rv0007 is the locus ID. Please consider all possible sources of information to conjecture reasonable function assignment."

python scientia_l33_v3.py $PROMPT > MTB.l33.txt &
python scientia_ds3_v3.py $PROMPT > MTB.ds3.txt &
python scientia_gpt45_v3.py $PROMPT > MTB.gpt45.txt &
python scientia_gpt4o_v3.py $PROMPT > MTB.gpt4o.txt &
