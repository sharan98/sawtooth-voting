#!/bin/python3

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------
import traceback
import sys
import hashlib
import logging

from sawtooth_sdk.processor.handler import TransactionHandler
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.processor.core import TransactionProcessor

DEFAULT_URL = 'tcp://validator:4004'

def hash(data):
    return hashlib.sha512(data.encode()).hexdigest()

logging.basicConfig(filename='example.log',level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

# namespaces
family_name = "voting"
FAMILY_NAME = hash(family_name)[:6]

VOTERS = hash("voters")[:6]
VOTER_LIST = hash("voters-list")
VOTERS_TABLE = FAMILY_NAME + VOTERS + VOTER_LIST[:58]

VOTING_ENTRIES = hash("voting-entries")[:6]
PARTIES = hash("parties")
PARTIES_TABLE = FAMILY_NAME + VOTING_ENTRIES + PARTIES[:58]

def getPartyAddress(partyName):
    return FAMILY_NAME + VOTING_ENTRIES + hash(partyName)[:58]

def getVoterAddress(voterName):
    voterName = str(voterName)
    return FAMILY_NAME + VOTERS + hash(voterName)[:58]

class VotingTransactionHandler(TransactionHandler):
    '''
    Transaction Processor class for the voting family
    '''
    def __init__(self, namespace_prefix):
        '''Initialize the transaction handler class.
        '''
        self._namespace_prefix = namespace_prefix

    @property
    def family_name(self):
        '''Return Transaction Family name string.'''
        return family_name

    @property
    def family_versions(self):
        '''Return Transaction Family version string.'''
        return ['1.0']

    @property
    def namespaces(self):
        '''Return Transaction Family namespace 6-character prefix.'''
        return [self._namespace_prefix]

    # Get the payload and extract the voting-specific information.
    # It has already been converted from Base64, but needs deserializing.
    # It was serialized with CSV: action, value
    def _unpack_transaction(self, transaction):
        header = transaction.header
        payload_list = self._decode_data(transaction.payload)
        return payload_list


    def apply(self, transaction, context):
        '''This implements the apply function for the TransactionHandler class.
        '''
        LOGGER.info ('starting apply function')
        try:
            payload_list = self._unpack_transaction(transaction)
            LOGGER.info ('payload: {}'.format(payload_list))
            action = payload_list[0]
            try:
                if action == "addparty":
                    partyName = payload_list[1]
                    self._addparty(context, partyName)
                elif action == "votefor":
                    voterName= payload_list[1]
                    partyName = payload_list[2]
                    self._voterfor(context, voterName, partyName)
                    action = payload_list[0]
                else:
                    LOGGER.debug("Unhandled action. Action should be addparty, votefor: " + action)
            except IndexError as i:
                # partyName = 'parties'
                LOGGER.debug ('IndexError: {}'.format(i))
                raise Exception()
        except Exception as e:
            raise InvalidTransaction("Error: {}".format(e))
            
    @classmethod
    def _voterfor(self, context, voterName, partyName):
        LOGGER.info("entering votefor")
        partyaddress = getPartyAddress(partyName)
        try:
            existing_parties= self._readData(context, PARTIES_TABLE)
            LOGGER.info ('existing_parties: {}'.format(existing_parties))
            if partyName in existing_parties:
                voters_list = self._readData(context, VOTERS_TABLE)
                LOGGER.info ('voters_list: {}'.format(voters_list))
                # if voters_list:
                    # voters_list = []
                if voterName not in voters_list:
                    initial_vote_count = self._readData(context, partyaddress)
                    LOGGER.info ('init_vote_count: {}'.format(initial_vote_count))
                    votes = int(initial_vote_count[0]) + 1
                    voters_list.append(voterName)
                    addresses = context.set_state({
                        VOTERS_TABLE: self._encode_data(voters_list),
                        partyaddress: self._encode_data(str(votes))
                    })        
                else:
                    pass
                    # raise InvalidTransaction('Voter has already voted.')
            else:
                pass
                # raise InvalidTransaction('Party doesn\'t exist.')
            LOGGER.info('{} voted for {}'.format(voterName, partyName))
        except TypeError as t:
            logging.debug('TypeError in _votefor: {}'.format(t))
            raise InvalidTransaction('Type error')
        except InvalidTransaction as e:
            logging.debug ('excecption: {}'.format(e))
            raise e
        except Exception as e:
            logging.debug('excecption: {}'.format(e))
            raise InvalidTransaction('excecption: {}'.format(e))

    @classmethod
    def _addparty(self, context, partyName):
        partyaddress = getPartyAddress(partyName)
        initial_vote_count = 0
        try:
            LOGGER.info("entering add")
            parties = self._readData(context, PARTIES_TABLE)  
            LOGGER.info ('Parties: {}'.format(parties))          
            if parties:
                if partyName not in parties:
                    print (parties)
                    parties.append(partyName)
                    LOGGER.info ("appended into list")
                else:
                    pass
                    # raise InvalidTransaction('{} already exists.'.format(partyName))
            else:
                parties = [partyName]
            parties = self._encode_data(parties)

            addresses = context.set_state({
                    PARTIES_TABLE: parties,
                    partyaddress: self._encode_data(str(initial_vote_count))
                })
        except Exception as e:
            logging.debug ('excecption: {}'.format(e))
            raise InvalidTransaction("State Error")

    # returns a list
    @classmethod
    def _readData(self, context, address):
        state_entries = context.get_state([address])
        if state_entries == []:
            return []
        data = self._decode_data(state_entries[0].data)
        return data

    # returns a list
    @classmethod
    def _decode_data(self, data):
        return data.decode().split(',')

    # returns a csv string
    @classmethod
    def _encode_data(self, data):
        return ','.join(data).encode()


def main():
    try:
        # Setup logging for this class.
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)

        # Register the Transaction Handler and start it.
        processor = TransactionProcessor(url=DEFAULT_URL)
        sw_namespace = FAMILY_NAME
        handler = VotingTransactionHandler(sw_namespace)
        processor.add_handler(handler)
        processor.start()
    except KeyboardInterrupt:
        pass
    except SystemExit as err:
        raise err
    except BaseException as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()