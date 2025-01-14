# source krypto/bin/activate

import datetime
import hashlib
import Crypto.Random
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_v1_5
import binascii
import base64
from uuid import uuid4

class Block:
    def __init__(self, index, prev_hash, block_data, transactions = [], timestamp = datetime.datetime.now(), nonce = 0):
        self.index = index
        self.block_data = block_data
        self.prev_hash = prev_hash
        self.transactions = transactions
        self.timestamp = timestamp
        self.nonce = nonce
        self.my_hash = self.hash_block()


    def hash_block(self):
        hashed_block = str(self.index) + str(self.block_data) + str(self.prev_hash) + "".join([str(t) for t in self.transactions])+ str(self.timestamp) + str(self.nonce)
        return hashlib.sha256(hashed_block.encode()).hexdigest()
    

    def mine_block(self, difficulty):
        while self.my_hash[:difficulty] != "0" * difficulty:
            self.nonce += 1
            self.my_hash = self.hash_block()
        return self.nonce


    def to_dict(self):
        return {
            "index": self.index,
            "data": self.block_data,
            "previous_hash": self.prev_hash,
            "transactions": [transaction.to_dict() for transaction in self.transactions],
            "timestamp": self.timestamp.isoformat(),
            "hash": self.my_hash,
            "nonce": self.nonce
        }
    
class Transaction:
    def __init__(self, sender, recipient, amount, signature, id=None, timestamp=None):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.signature = signature
        self.id = id if id else str(uuid4())
        self.timestamp = timestamp if timestamp else datetime.datetime.now().isoformat()


    def to_dict(self):
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "signature": self.signature,
            "id": self.id,
            "timestamp": self.timestamp
        }

    def is_valid(self):
        try:
            if self.amount <= 0:
                print("Invalid Amount")
                return False
            if self.sender == "coinbase":
                with open("coinbase.pem", "rb") as f:
                    coinbase = RSA.importKey(f.read())
                    hash_message = SHA.new("Reward Transaction".encode('utf8'))
                    signer = PKCS1_v1_5.new(coinbase)
                    return signer.verify(hash_message, binascii.unhexlify(self.signature))
            else:
                key = RSA.importKey(binascii.unhexlify(self.sender))
                verifier = PKCS1_v1_5.new(key)
                recipent_key = RSA.importKey(binascii.unhexlify(self.recipient))
                s_pkey = base64.b64encode(key.exportKey(format='DER')).decode('utf-8')
                r_pkey = base64.b64encode(recipent_key.exportKey(format='DER')).decode('utf-8')
                hash_message = SHA.new(f"{s_pkey}{r_pkey}{self.amount}{self.id}{self.timestamp}".encode('utf8'))
                return verifier.verify(hash_message, binascii.unhexlify(self.signature))
        except Exception as e:
            print(e)
            return False

    def __str__(self):
        return f"{self.sender} -> {self.recipient} : {self.amount} KryptoCoins, Signature: {self.signature}, ID: {self.id}, Timestamp: {self.timestamp}"
    


class BlockChain:
    def __init__(self, difficulty = 1):
        self.difficulty = difficulty
        self.current_transactions = []
        with open("coinbase.pem", "rb") as f:
            coinbase = RSA.importKey(f.read())
            hash_message = SHA.new("Reward Transaction".encode('utf8'))
            signer = PKCS1_v1_5.new(coinbase)
            first_transaction = Transaction("coinbase", "coinbase", 50, binascii.hexlify(signer.sign(hash_message)).decode('ascii'))
        self.chain = [Block(0, "0", "Genesis Block", [first_transaction])]


    def restore(self, chain):
        blocks = [Block(block['index'],
                            block['previous_hash'],
                            block['data'],
                            [Transaction(transation['sender'],
                                          transation['recipient'],
                                          transation['amount'],
                                          transation['signature'],
                                          transation['id'],
                                          transation['timestamp']) for transation in block['transactions']],        
                            datetime.datetime.fromisoformat(block['timestamp']),
                            block['nonce']
                    ) for block in chain]
        self.chain = [blocks[0]]
        for block in blocks[1:]:
            output = self.add_block(block)
            if not output:
                return False
        return True

    def get_latest_block(self):
        return self.chain[-1]
    

    def add_transaction(self, transaction):
        if not transaction.is_valid():
            print("Invalid Transaction")
            return False
        for transaction in self.current_transactions:
            if transaction.sender == transaction.sender and transaction.recipient == transaction.recipient:
                print("Possible Double Spending")
                return False # Possible Double Spending
        self.current_transactions.append(transaction)
        return True


    def mine(self, miner):
        with open("coinbase.pem", "rb") as f:
            coinbase = RSA.importKey(f.read())
            signer = PKCS1_v1_5.new(coinbase)
            hash_message = SHA.new("Reward Transaction".encode('utf8'))
            self.current_transactions.insert(0, Transaction("coinbase", miner, 50, binascii.hexlify(signer.sign(hash_message)).decode('ascii')))

        new_block = Block(self.get_latest_block().index + 1, self.get_latest_block().my_hash, "Block Data", self.current_transactions)
        new_block.mine_block(self.difficulty)
        self.current_transactions = []
        return new_block

    def mine_bad_block(self, miner):
        with open("coinbase.pem", "rb") as f:
            coinbase = RSA.importKey(f.read())
            signer = PKCS1_v1_5.new(coinbase)
            hash_message = SHA.new("Reward Transaction".encode('utf8'))
            self.current_transactions.insert(0, Transaction("coinbase", miner, 50, binascii.hexlify(signer.sign(hash_message)).decode('ascii')))

        new_block = Block(self.get_latest_block().index + 1, "bad_previous_hash", "Bad Block Data", self.current_transactions)
        new_block.mine_block(self.difficulty)
        self.current_transactions = []
        return new_block

    def is_valid_new_block(self, new_block, prev_block):
        if prev_block.index + 1 != new_block.index:
            print("Index Error")
            return False
        elif prev_block.my_hash != new_block.prev_hash:
            print("Hash Error")
            return False
        elif new_block.hash_block() != new_block.my_hash:
            print("Hash Block Error")
            return False
        has_coinbase_transaction = False
        for transaction in new_block.transactions:
            if not transaction.is_valid():
                print("Transaction Error")
                return False
            if transaction.sender == "coinbase":
                if has_coinbase_transaction:
                    print("Duplicate Coinbase Transaction")
                    return False
                has_coinbase_transaction = True
        return True
    

    def add_block(self, new_block):
        if self.is_valid_new_block(new_block, self.get_latest_block()):
            self.chain.append(new_block)
            return True
        return False
    

    def to_dict(self):
        return [block.to_dict() for block in self.chain]
    

class Wallet:
    def __init__(self, init = False):
        if init:
            self._private_key = RSA.generate(4096, Crypto.Random.new().read)
            self._public_key = self._private_key.publickey()
            self._signer = PKCS1_v1_5.new(self._private_key)
        else:
            self._private_key = None
            self._public_key = None
            self._signer = None
    
    
    def encode(self):
        return {
            "private_key": base64.b64encode(self._private_key.exportKey(format='DER')).decode('utf-8'),
            "public_key": base64.b64encode(self._public_key.exportKey(format='DER')).decode('utf-8')
        }
    

    def decode(self, encoded):
        self._private_key = RSA.importKey(base64.b64decode(encoded['private_key']))
        self._public_key = RSA.importKey(base64.b64decode(encoded['public_key']))
        self._signer = PKCS1_v1_5.new(self._private_key)


    @property
    def identity(self):
        return binascii.hexlify(self._public_key.exportKey(format='DER')).decode('ascii')
    

    def sign(self, message):
        h = SHA.new(message.encode('utf8'))
        return binascii.hexlify(self._signer.sign(h)).decode('ascii')
    

    def verify(self, message, signature, signer):
        h = SHA.new(message.encode('utf8'))
        verifier = PKCS1_v1_5.new(signer)
        return verifier.verify(h, binascii.unhexlify(signature))
    

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