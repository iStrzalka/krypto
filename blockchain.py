# source krypto/bin/activate

import datetime
import hashlib
import Crypto.Random
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_v1_5
import binascii
import base64

class Block:
    def __init__(self, index, prev_hash, block_data, transactions = [], timestamp = datetime.datetime.now(), nonce = 0):
        self.index = index
        self.block_data = block_data
        self.prev_hash = prev_hash
        self.transactions = transactions
        self.timestamp = timestamp
        self.nonce = 0
        self.my_hash = self.hash_block()


    def hash_block(self):
        hashed_block = str(self.index) + str(self.block_data) + str(self.prev_hash) + str(self.transactions)+ str(self.timestamp) + str(self.nonce)
        return hashlib.sha256(hashed_block.encode()).hexdigest()
    

    def mine_block(self, difficulty):
        while self.my_hash[:difficulty] != "0" * difficulty:
            self.nonce += 1
            self.my_hash = self.hash_block()


    def to_dict(self):
        return {
            "index": self.index,
            "data": self.block_data,
            "previous_hash": self.prev_hash,
            "transactions": [transaction.to_dict() for transaction in self.transactions],
            "timestamp": self.timestamp.isoformat(),
            "hash": self.my_hash
        }
    
class Transaction:
    def __init__(self, sender, recipient, amount, signature):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.signature = signature


    def to_dict(self):
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "signature": self.signature
        }


    def __str__(self):
        return f"{self.sender} -> {self.recipient} : {self.amount} KryptoCoins, Signature: {self.signature}"
    


class BlockChain:
    def __init__(self, difficulty = 1):
        self.coinbase = Wallet()     
        self.difficulty = difficulty
        self.current_transactions = []
        self.chain = [Block(0, "0", "Genesis Block", [Transaction("0", self.coinbase.identity, 50, "")])]


    def restore(self, chain, coinbase):
        self.coinbase.decode(coinbase)
        self.chain = [Block(block['index'],
                            block['previous_hash'],
                            block['data'],
                            [Transaction(transation['sender'],
                                          transation['recipient'],
                                          transation['amount'],
                                          transation['signature']) for transation in block['transactions']],        
                            datetime.datetime.fromisoformat(block['timestamp']),
                    ) for block in chain]


    def get_latest_block(self):
        return self.chain[-1]
    

    def add_transaction(self, transaction):
        self.current_transactions.append(transaction)


    def mine(self, miner):
        new_block = Block(self.get_latest_block().index + 1, self.get_latest_block().my_hash, "Block Data", self.current_transactions)
        new_block.mine_block(self.difficulty)
        self.current_transactions = [Transaction(self.coinbase.identity, miner, 50, self.coinbase.sign("50"))]
        self.chain.append(new_block)
        return new_block


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
        self._private_key = RSA.generate(4096, Crypto.Random.new().read)
        self._public_key = self._private_key.publickey()
        self._signer = PKCS1_v1_5.new(self._private_key)
    
    
    def encode(self):
        return {
            "private_key": base64.b64encode(self._private_key.exportKey(format='DER')).decode('utf-8'),
            "public_key": base64.b64encode(self._public_key.exportKey(format='DER')).decode('utf-8')
        }
    

    def decode(self, encoded):
        self._private_key = RSA.importKey(base64.b64decode(encoded['private_key']))
        self._public_key = RSA.importKey(base64.b64decode(encoded['public_key']))


    @property
    def identity(self):
        return binascii.hexlify(self._public_key.exportKey(format='DER')).decode('ascii')
    

    def sign(self, message):
        h = SHA.new(message.encode('utf8'))
        return binascii.hexlify(self._signer.sign(h)).decode('ascii')
    

    def to_dict(self):
        return {
            "private_key": base64.b64encode(self._private_key.exportKey(format='DER')).decode('utf-8'),
            "public_key": base64.b64encode(self._public_key.exportKey(format='DER')).decode('utf-8')
        }



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