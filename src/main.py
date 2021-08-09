#!/usr/bin/env python3
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import os
import sys
import pprint
import numpy as np

BLOCK_SIZE_BYTES = 1000000
# BLOCK_SIZE_BYTES = 1000 

SATS_PER_BTC = 100000000

class MempoolBytesPerFeeLevel():

    def __init__(self, rpc_user, rpc_pass, rpc_host, rpc_port):
        self.rpc_connection = AuthServiceProxy("http://%s:%s@%s:%s" % (rpc_user, rpc_pass, rpc_host, rpc_port))

    def getInputValue(self, txid, vout):
            serialized_tx = self.rpc_connection.decoderawtransaction(self.rpc_connection.getrawtransaction(txid))
            output = next((d for (index, d) in enumerate(serialized_tx['vout']) if d["n"] == vout), None)
            return output['value']

    def get_fee(self, tx):
            ## returns in sats
            ## Add up output values
            output_value = 0
            [output_value:= output_value + vout['value'] for vout in tx['vout']]
            ## Add up input values
            input_value = 0
            [input_value:= input_value + self.getInputValue(vin['txid'], vin['vout']) for vin in tx['vin']]

            assert(input_value > output_value)
            return float((input_value - output_value) * SATS_PER_BTC)

    def get_mempool_bytes_per_fee_level(self):
        mempool = self.rpc_connection.getrawmempool(False)
        txs = []
        # 1. Data extraction 
        # Need total miner revenue and tx size
        for txid in mempool:
            try:
                serialized_tx = self.rpc_connection.decoderawtransaction(self.rpc_connection.getrawtransaction(txid))
                fee = self.get_fee(serialized_tx)
                txs.append({'txid': serialized_tx['txid'],'fee': fee , 'fee_rate': fee / serialized_tx['size'] , 'size': serialized_tx['size']})
            except Exception as error:
                print('Exception thrown when deserialzing tx', error)
                continue
        # 2. Sort mempool txs by miner revenue
        txs = sorted(txs, key=lambda k: k['fee_rate']) 
        # 3. Create buckets of next block perdictions
        block_targets = [[]]
        size_counter = 0
        block_index = 0
        for _, tx in enumerate(txs):
            if(size_counter > BLOCK_SIZE_BYTES or size_counter + tx['size'] > BLOCK_SIZE_BYTES):
                #  3.1 start a new block since we are running out of space
                block_targets.append([])
                block_index += 1
            block_targets[block_index].append(tx['fee_rate'])
        # 4. get highest, median, lowest fee rates per block target
        targets = [ {'.9': np.percentile(np.array(block), 90), '.5': np.percentile(np.array(block), 50), '.10': np.percentile(np.array(block), 10)} for block in block_targets]
        return targets
        # print(block_targets)
if __name__ == "__main__":
    if ('RPC_USER' not in os.environ
        or 'RPC_PASSWORD' not in os.environ
        or 'RPC_HOST' not in os.environ
        or 'RPC_PORT' not in os.environ) :
            raise Exception('Must specify RPC_USER and RPC_PASSWORD, RPC_HOST, RPC_PORT environs')

    pp = pprint.PrettyPrinter(indent=4)
    fee_buckets = MempoolBytesPerFeeLevel(os.environ['RPC_USER'], os.environ['RPC_PASSWORD'], os.environ['RPC_HOST'], os.environ['RPC_PORT'])
    fees = fee_buckets.get_mempool_bytes_per_fee_level()
    pp.pprint(fees)
    


