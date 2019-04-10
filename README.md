# sawtooth-voting
A hyperledger sawtooth application for voting  
The application uses blockchain and docker containers to store the parties, voter IDs and vote count.  

## Instructions for use
Build the necessary components used by the application using docker-compose.yaml file by running:  
  `[sudo] docker-compose up`  
  Run the client.py file as shown below, inside the container voting-client :  
  `docker exec -it voting-client bash`  
  Now we are inside the client docker.
## Use cases and commands
 #### 1. Add parties
 Parties are identified by their names. Parties can be added exactly once.  
 `python3 vote.py addparty PartyName [--url http://rest-api:8008]`  
 #### 2. Cast votes
 Voters can cast vote exactly once and for exactly one party; voters are identified by their names.  
 `python3 vote.py votefor VoterName PartyName`  
 #### 3. List parties and voters
 List all added parties and voters who have voted.  
 `python3 vote.py listparties`  
 `python3 vote.py listvotes`  
 #### 4. Number of votes
 Number of votes of each party.  
 `python3 vote.py votecount PartyName`
