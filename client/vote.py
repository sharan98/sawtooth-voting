#!/bin/python3
import hashlib
import base64
import random
import time
import requests
import yaml
import sys
import logging
import optparse
from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch

logging.basicConfig(filename='client.log',level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

parser = optparse.OptionParser()
parser.add_option('-U', '--url', action = "store", dest = "url", default = "http://rest-api:8008")

def hash(data):
    return hashlib.sha512(data.encode()).hexdigest()

# namespaces : voting + voters/voting-entries + voterlist/partieslist
family_name = "voting"
FAMILY_NAME = hash(family_name)[:6]

VOTERS = hash("voters")[:6]
VOTER_LIST = hash("voters-list")
VOTERS_TABLE = FAMILY_NAME + VOTERS + VOTER_LIST[:58]

VOTING_ENTRIES = hash("voting-entries")[:6]
PARTIES = hash("parties")
PARTIES_TABLE = FAMILY_NAME + VOTING_ENTRIES + PARTIES[:58]

# random private key
context = create_context('secp256k1')
private_key = context.new_random_private_key()
signer = CryptoFactory(context).new_signer(private_key)
public_key = signer.get_public_key().as_hex()

base_url = ''

def getPartyAddress(partyName):
    return FAMILY_NAME + VOTING_ENTRIES + hash(partyName)[:58]

def getVoterAddress(voterName):
    voterName = str(voterName)
    return FAMILY_NAME + VOTERS + hash(voterName)[:58]

def addParty(partyName):
    logging.info ('addparty({})'.format(partyName))
    input_address_list = [PARTIES_TABLE]
    output_address_list = [PARTIES_TABLE, getPartyAddress(partyName)]
    response = wrap_and_send("addparty", partyName, input_address_list, output_address_list, wait = 5)
    print ("add response: {}".format(response))
    return yaml.safe_load(response)['data'][0]['status']

def castVote(voter, partyName):
    l = [voter, partyName]
    command_string = ','.join(l)
    partyaddress = getPartyAddress(partyName)
    input_address_list = [PARTIES_TABLE, VOTERS_TABLE, partyaddress]
    output_address_list = [PARTIES_TABLE, VOTERS_TABLE, partyaddress]
    response = wrap_and_send("votefor", command_string, input_address_list, output_address_list, wait = 5)
    # print ("add response: {}".format(response))
    return yaml.safe_load(response)['data'][0]['status']

def getPartyVoteCount(partyName):
    result = send_to_rest_api("state/{}".format(getPartyAddress(partyName)))
    try:
        return (base64.b64decode(yaml.safe_load(result)["data"])).decode()
    except BaseException:
        return None

def listParties():
    result = send_to_rest_api("state/{}".format(PARTIES_TABLE))
    try:
        return (base64.b64decode(yaml.safe_load(result)["data"])).decode()
    except BaseException:
        return None

def listVoters():
    result = send_to_rest_api("state/{}".format(VOTERS_TABLE))
    try:
        return (base64.b64decode(yaml.safe_load(result)["data"])).decode()
    except BaseException:
        return None

def send_to_rest_api(suffix, data=None, content_type=None):
    url = "{}/{}".format(base_url, suffix)
    headers = {}
    logging.info ('sending to ' + url)
    if content_type is not None:
        headers['Content-Type'] = content_type

    try:
        if data is not None:
            result = requests.post(url, headers=headers, data=data)
            logging.info ("\nrequest sent POST\n")
        else:
            result = requests.get(url, headers=headers)
        if not result.ok:
            logging.debug ("Error {}: {}".format(result.status_code, result.reason))
            raise Exception("Error {}: {}".format(result.status_code, result.reason))
    except requests.ConnectionError as err:
        logging.debug ('Failed to connect to {}: {}'.format(url, str(err)))
        raise Exception('Failed to connect to {}: {}'.format(url, str(err)))
    except BaseException as err:
        raise Exception(err)
    return result.text

def wait_for_status(batch_id, result, wait = 10):
    '''Wait until transaction status is not PENDING (COMMITTED or error).
        'wait' is time to wait for status, in seconds.
    '''
    if wait and wait > 0:
        waited = 0
        start_time = time.time()
        logging.info ('url : ' + base_url + "batch_statuses?id={}&wait={}".format(batch_id, wait))
        while waited < wait:
            result = send_to_rest_api("batch_statuses?id={}&wait={}".format(batch_id, wait))
            status = yaml.safe_load(result)['data'][0]['status']
            waited = time.time() - start_time

            if status != 'PENDING':
                return result
        logging.debug ("Transaction timed out after waiting {} seconds.".format(wait))
        return "Transaction timed out after waiting {} seconds.".format(wait)
    else:
        return result


def wrap_and_send(action, partyName, input_address_list, output_address_list, wait=None):
    '''Create a transaction, then wrap it in a batch.
    '''
    payload = ",".join([action, str(partyName)])
    logging.info ('payload: {}'.format(payload))

    # Construct the address where we'll store our state.
    # Create a TransactionHeader.
    header = TransactionHeader(
        signer_public_key = public_key,
        family_name = family_name,
        family_version = "1.0",
        inputs = input_address_list,         # input_and_output_address_list,
        outputs = output_address_list,       # input_and_output_address_list,
        dependencies = [],
        payload_sha512 = hash(payload),
        batcher_public_key = public_key,
        nonce = random.random().hex().encode()
    ).SerializeToString()

    # Create a Transaction from the header and payload above.
    transaction = Transaction(
        header = header,
        payload = payload.encode(),                 # encode the payload
        header_signature = signer.sign(header)
    )

    transaction_list = [transaction]

    # Create a BatchHeader from transaction_list above.
    header = BatchHeader(
        signer_public_key = public_key,
        transaction_ids = [txn.header_signature for txn in transaction_list]
    ).SerializeToString()

    # Create Batch using the BatchHeader and transaction_list above.
    batch = Batch(
        header = header,
        transactions = transaction_list,
        header_signature = signer.sign(header)
    )

    # Create a Batch List from Batch above
    batch_list = BatchList(batches=[batch])
    batch_id = batch_list.batches[0].header_signature
    # Send batch_list to the REST API
    result = send_to_rest_api("batches", batch_list.SerializeToString(), 'application/octet-stream')

    # Wait until transaction status is COMMITTED, error, or timed out
    return wait_for_status(batch_id, result, wait = wait)

if __name__ == '__main__':
    try:
        opts, args = parser.parse_args()
        base_url = opts.url
        if sys.argv[1] == "addparty":
            logging.info ('addparty command: ' + sys.argv[2])
            result = addParty(sys.argv[2])
            if result == 'COMMITTED':
                logging.info (sys.argv[2] + " added")
                print ("\nParty added " + sys.argv[2])
            else:
                logging.info (sys.argv[2] + " not added")
                print ("\n{} not added ".format(sys.argv[2]))
        elif sys.argv[1] == "votefor":
            logging.info ('votefor command: voter: {}, party: {}'.format(sys.argv[2], sys.argv[3]))
            result = castVote(sys.argv[2], sys.argv[3])
            if result == 'COMMITTED':
                logging.info ('voted for ' + sys.argv[2])
                print ("\nCasted vote for " + sys.argv[2])
            else:
                logging.info ('Didn\'t voted for ' + sys.argv[2])
                print ("\nDidn\'t Cast vote for " + sys.argv[2])
        elif sys.argv[1] == "votecount":
            logging.info ('command : votecount for ' + sys.argv[2])
            result = getPartyVoteCount(sys.argv[2])
            print ('No.of votes for {}: {}'.format (sys.argv[2], result))
        elif sys.argv[1] == "listparties":
            logging.info ('command : listparties')
            result = listParties()
            print ('The Parties: {}'.format (result))
        elif sys.argv[1] == "listvoters":
            logging.info ('command : listvoters')
            result = listVoters()
            print ('The Voters: {}'.format (result))
    except IndexError as i:
        logging.debug ('party name not entered')
        print ('Enter party name.')
        print (i)
    except Exception as e:
        print (e)