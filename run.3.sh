#!/bin/bash

PROMPT="Please develop strategies for partnering between the DOE national labs and the US based AI research labs, such as openAI, Anthropic, Google DeepMind, xAI and Meta. Please describe novel partnering mechanisms and strategic breakthroughs that are possible that would advance scientific research and economic development."

python scientia_l33_v3.py $PROMPT > AIP.l33.txt &
python scientia_ds3_v3.py $PROMPT > AIP.ds3.txt &
python scientia_gpt4o_v3.py $PROMPT > AIP.gpt4o.txt &
python scientia_gpt45_v3.py $PROMPT > AIP.gpt45.txt &
