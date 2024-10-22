# source krypto/bin/activate

import datetime
import hashlib
import Crypto.Random
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_v1_5
import binascii

class Block:
    def __init__(self, index, prev_hash, block_data, timestamp = datetime.datetime.now()):
        self.index = index
        self.block_data = block_data
        self.prev_hash = prev_hash
        self.timestamp = timestamp
        self.my_hash = self.hash_block()


    def hash_block(self):
        hashed_block = "{}{}{}{}".format(self.index, self.prev_hash, self.block_data, self.timestamp)
        return hashlib.sha256(hashed_block.encode()).hexdigest()
    
    def to_dict(self):
        return {
            "index": self.index,
            "data": self.block_data,
            "previous_hash": self.prev_hash,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.my_hash
        }
    

class BlockChain:
    def __init__(self):
        self.chain = [Block(0, "0", "Genesis Block")]     

    def restore(self, chain):
        self.chain = [Block(block['index'], block['previous_hash'], block['data'], datetime.datetime.fromisoformat(block['timestamp'])) for block in chain]

    def get_latest_block(self):
        return self.chain[-1]
   
    def generate_next_block(self, data):
        prev_block = self.get_latest_block()
        next_index = prev_block.index + 1
        next_prev_hash = prev_block.my_hash
        next_block = Block(next_index, next_prev_hash, data)
        self.add_block(next_block)
        return next_block

    def is_valid_new_block(self, new_block, prev_block):
        if prev_block.index + 1 != new_block.index:
            return False
        elif prev_block.my_hash != new_block.prev_hash:
            return False
        elif new_block.hash_block() != new_block.my_hash:
            return False
        return True
    

    def add_block(self, new_block):
        if self.is_valid_new_block(new_block, self.get_latest_block()):
            self.chain.append(new_block)
            return True
        return False
    

    def to_dict(self):
        return [block.to_dict() for block in self.chain]
    

class Wallet:
    def __init__(self):
        self._private_key = RSA.generate(1024, Crypto.Random.new().read)
        self._public_key = self._private_key.publickey()
        self._signer = PKCS1_v1_5.new(self._private_key)
    
    @property
    def identity(self):
        return binascii.hexlify(self._public_key.exportKey(format='DER')).decode('ascii')
    
    def sign(self, message):
        h = SHA.new(message.encode('utf8'))
        return binascii.hexlify(self._signer.sign(h)).decode('ascii')
    

if __name__ == '__main__':
    blockchain = BlockChain()

    blockchain.generate_next_block("What")
    blockchain.generate_next_block("is")
    blockchain.generate_next_block("Blockchain")
    blockchain.generate_next_block("Technology")
    blockchain.generate_next_block("and")
    blockchain.generate_next_block("how")
    blockchain.generate_next_block("does")
    blockchain.generate_next_block("it")
    blockchain.generate_next_block("work")

    for block in blockchain.chain:
        print("Index: ", block.index)
        print("Data: ", block.block_data)
        print("Previous Hash: ", block.prev_hash)
        print("Timestamp: ", block.timestamp)
        print("Hash: ", block.my_hash)
        print("\n")