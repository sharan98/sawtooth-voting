#!/bin/bash
python3 vote.py addparty PartyA
python3 vote.py addparty PartyB
python3 vote.py addparty PartyC
python3 vote.py votefor Sharan PartyA
python3 vote.py votefor ABC PartyB
sawtooth state list --url http://rest-api:8008
python3 vote.py votefor ABCD PartyB
sawtooth state list --url http://rest-api:8008
sawtooth block list --url http://rest-api:8008
python3 vote.py votefor ABC PartyB
python3 vote.py addparty PartyC
