import socket
import threading
import sys

from defaults import *
import datetime
from blockchain import BlockChain, Transaction, Block
import time

import json

RECV_BUFFER = 16384 * 16384

class P2P:
    def __init__(self, host, port, init):
        self.host = host
        self.port = port
        self.known_peers = []
        self.blockchain = BlockChain() if init else None
        self.server_socket = None
        self.running = True
        self.recv_accept = True
        self.last_option = ""


    def handle_peer_connection(self, conn, addr):
        m_type = None
        try:
            message = json.loads(conn.recv(RECV_BUFFER).decode('utf-8'))
            m_type = message['type']
            if message['type'] == 'hello':
                if message['port'] not in self.known_peers:
                    self.known_peers.append(message['port'])
                if self.blockchain is None:
                    self.blockchain = BlockChain()
                    self.blockchain.restore(message['blockchain'])
                    conn.send(json.dumps({
                        "type": "hello-recv",
                        "port": my_port,
                        "send_back" : False,
                    }).encode('utf-8'))
                else:
                    conn.send(json.dumps({
                        "type": "hello",
                        "port": my_port,
                        "send_back" : True,
                        "blockchain": self.blockchain.to_dict()
                    }).encode('utf-8'))

            if message['type'] == 'broadcast':
                output = False
                if message['data']['type'] == 'new_block':
                    print("Received new block")
                    block_data = message['data']['block']
                    block = Block(block_data['index'],
                                block_data['previous_hash'],
                                block_data['data'],
                                [Transaction(transation['sender'],
                                                transation['recipient'],
                                                transation['amount'],
                                                transation['signature'],
                                                transation['id'],
                                                transation['timestamp']) for transation in block_data['transactions']],        
                                datetime.datetime.fromisoformat(block_data['timestamp']))
                    output = self.blockchain.add_block(block)
                    if output == True:
                        self.blockchain.current_transactions = []
                if message['data']['type'] == 'add_transaction':
                    transaction = Transaction(message['data']['transaction']['sender'], message['data']['transaction']['recipient'], message['data']['transaction']['amount'], message['data']['transaction']['signature'], message['data']['transaction']['id'], message['data']['transaction']['timestamp'])
                    output = self.blockchain.add_transaction(transaction)
                if message['data']['type'] == 'tree':
                    output = True
                if output == False:
                    conn.send(json.dumps({
                        "type": "broadcast-recv",
                        "ports_visited": [],
                        "edges" : [],
                        "result": False
                    }).encode('utf-8'))
                else:
                    self.last_option = message['data']['type']
                    sent_to, edges, output = self.broadcast(message['ports_visited'], message['data'])
                    conn.send(json.dumps({
                        "type": "broadcast-recv",
                        "ports_visited": sent_to,
                        "edges" : edges,
                        "result": output
                    }).encode('utf-8'))    

            if message['type'] == 'ping':
                conn.send(json.dumps({
                    "type": "pong"
                }).encode('utf-8'))

            if message['type'] == 'tree':
                sent_to, edges, success = self.broadcast([], {"type": "tree"})
                conn.send(json.dumps({
                    "type": "tree-recv",
                    "edges" : edges,
                    "ports_visited": sent_to,
                    "result": success
                }).encode('utf-8'))

            if message['type'] == 'request_blockchain':
                if self.blockchain is not None:
                    conn.send(json.dumps({
                        "type": "send_blockchain",
                        "blockchain": self.blockchain.to_dict()
                    }).encode('utf-8'))
                else:
                    conn.send(json.dumps({
                        "type": "send_blockchain",
                        "blockchain": None
                    }).encode('utf-8'))

            if message['type'] == 'add_transaction':
                if self.blockchain is not None:
                    transaction = Transaction(message['sender'], message['recipient'], message['amount'], message['signature'], message['id'], message['timestamp'])
                    success1 = self.blockchain.add_transaction(transaction)
                    if success1:
                        _, _, success = self.broadcast([], {"type": "add_transaction", "transaction": transaction.to_dict()})
                    else:
                        success = True
                    
                    if not success:
                        print("Transaction failed, need to sync")
                        return_to_sender = self.sync()
                        conn.send(json.dumps({
                            "type": "add_transaction_recvt",
                            "success": success and success1,
                            "transactions": return_to_sender
                        }).encode('utf-8'))
                    else:
                        conn.send(json.dumps({
                            "type": "add_transaction_recv",
                            "success": success and success1
                        }).encode('utf-8'))
                else:
                    conn.send(json.dumps({
                        "type": "add_transaction_recv",
                        "success": False
                    }).encode('utf-8'))

            if message['type'] == 'mine':
                if self.blockchain is not None:
                    block = self.blockchain.mine(message['miner'])
                    _, _, success = self.broadcast([], {"type": "new_block", "block": block.to_dict()})
                    
                    if success:
                        self.blockchain.add_block(block)
                        self.blockchain.current_transactions = []
                        conn.send(json.dumps({
                            "type": "mine",
                            "success": success
                        }).encode('utf-8'))
                    else:
                        print("Mining failed, need to sync")
                        return_to_sender = self.sync()
                        conn.send(json.dumps({
                            "type": "mine_recvt",
                            "success": success,
                            "transactions": return_to_sender
                        }).encode('utf-8'))
                else:
                    conn.send(json.dumps({
                        "type": "mine",
                        "success": False
                    }).encode('utf-8'))            

            if message['type'] == 'request_blockchain_transactions':
                if self.blockchain is not None:
                    conn.send(json.dumps({
                        "type": "send_blockchain_transactions",
                        "transactions": [transaction.to_dict() for transaction in self.blockchain.current_transactions]
                    }).encode('utf-8'))
                else:
                    conn.send(json.dumps({
                        "type": "send_blockchain_transactions",
                        "transactions": None
                    }).encode('utf-8'))
            
            if message['type'] == 'sync_request':
                conn.send(json.dumps({
                    "type": "sync_response",
                    "blockchain": self.blockchain.to_dict(),
                    "current_transactions": [transaction.to_dict() for transaction in self.blockchain.current_transactions]
                }).encode('utf-8'))
            
            if message['type'] == 'sync_complete':
                result = self.blockchain.restore(message['blockchain'])
                self.blockchain.current_transactions = [Transaction(transaction['sender'], 
                                                                    transaction['recipient'], 
                                                                    transaction['amount'], 
                                                                    transaction['signature'], 
                                                                    transaction['id'], 
                                                                    transaction['timestamp']) for transaction in message['current_transactions']]
                conn.send(json.dumps({
                    "type": "sync_complete",
                    "result": result
                }).encode('utf-8'))

            if message['type'] == 'produce_bad_fork':
                if self.blockchain is not None:
                    bad_block = self.blockchain.mine_bad_block(message['miner'])
                    self.blockchain.chain.append(bad_block)
                    self.blockchain.current_transactions = []
                    conn.send(json.dumps({
                        "type": "produce_bad_fork",
                        "success": True
                    }).encode('utf-8'))
                else:
                    conn.send(json.dumps({
                        "type": "produce_bad_fork",
                        "success": False
                    }).encode('utf-8'))
        except Exception as e:
            print('handle_peer_connection', m_type, e)
            raise e
        conn.close()


    def broadcast(self, previously_sent_to, data):
        sent_to = previously_sent_to + [self.port]
        edges = []
        success = True
        for peer in self.known_peers:
            edges.append([self.port, peer])
            if peer in sent_to:
                continue
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((self.host, peer))
                conn.send(json.dumps({
                    "type": "broadcast",
                    "ports_visited": sent_to,
                    "data": data
                }).encode('utf-8'))
                
                recv_data = conn.recv(RECV_BUFFER)

                message = json.loads(recv_data.decode('utf-8'))
                success = message['result']
                if not success:
                    if self.last_option == 'add_transaction':
                        self.blockchain.current_transactions.pop()
                    if self.last_option == 'new_block':
                        self.blockchain.chain.pop()
                    break
                sent_to = message['ports_visited']
                for edge in message['edges']:
                    edges.append(edge)
                conn.close()
            except ConnectionRefusedError:
                edges.remove([self.port, peer])
            except Exception as e:
                print(e)
                break
        return sent_to, edges, success
    

    def sync(self):
        all_peers, _, _ = self.broadcast([], {"type": "tree"})
        all_blockchains, all_current_transactions = [], [self.blockchain.current_transactions]
        print(all_peers)
        for peer in all_peers:
            if peer == self.port:
                continue
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((self.host, peer))
                conn.send(json.dumps({
                    "type": "sync_request"
                }).encode('utf-8'))
                conn.settimeout(1)
                data = conn.recv(RECV_BUFFER)
                
                message = json.loads(data.decode('utf-8'))
                if message['type'] == 'sync_response':
                    if message['blockchain'] is not None:
                        all_blockchains.append(message['blockchain'])
                    if message['current_transactions'] is not None:
                        all_current_transactions.append(message['current_transactions'])
                conn.close()
            except Exception as e:
                print('sync', e)
                return

        # Choose the longest valid blockchain
        correct_blockchains = []
        for i, possible_blockchain in enumerate(all_blockchains):
            bk = BlockChain()
            result = bk.restore(possible_blockchain)
            if result:
                correct_blockchains.append(bk)
        correct_blockchains.append(self.blockchain)
        chosen_blockchain = max(correct_blockchains, key=lambda x: len(x.chain))
        self.blockchain = chosen_blockchain
        
        # Get all transactions from selected blockchain
        all_transactions = []
        for block in self.blockchain.chain:
            for transaction in block.transactions:
                all_transactions.append(transaction)
        
        # Add unused forked transactions to mempool 
        # Here: Adding them back to wallets of the sender
        return_to_sender = {}
        for bk in correct_blockchains:
            if bk == chosen_blockchain:
                continue
            for block in bk.chain:
                for transaction in block.transactions:
                    if transaction not in all_transactions:
                        if transaction.sender == 'coinbase':
                            return_to_sender[transaction.recipient] = return_to_sender.get(transaction.recipient, 0) - transaction.amount
                        else:
                            return_to_sender[transaction.sender] = return_to_sender.get(transaction.sender, 0) + transaction.amount
                            return_to_sender[transaction.recipient] = return_to_sender.get(transaction.recipient, 0) - transaction.amount


        for transactions in all_current_transactions:
            ts = [Transaction(transaction['sender'], transaction['recipient'], transaction['amount'], transaction['signature'], transaction['id'], transaction['timestamp']) for transaction in transactions]
            for transaction in ts:
                if transaction not in all_transactions:
                    if transaction.sender == 'coinbase':
                        return_to_sender[transaction.recipient] = return_to_sender.get(transaction.recipient, 0) - transaction.amount
                    else:
                        return_to_sender[transaction.sender] = return_to_sender.get(transaction.sender, 0) + transaction.amount
                        return_to_sender[transaction.recipient] = return_to_sender.get(transaction.recipient, 0) - transaction.amount

        if 'coinbase' in return_to_sender:
            del return_to_sender['coinbase']

        print("Synced")
        print(len(correct_blockchains), len(all_peers), all_peers)
        sync_fail = []
        for peer in all_peers:
            if peer == self.port:
                continue
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((self.host, peer))
                conn.send(json.dumps({
                    "type": "sync_complete",
                    "blockchain": self.blockchain.to_dict(),
                    "current_transactions": [transaction.to_dict() for transaction in self.blockchain.current_transactions]
                }).encode('utf-8'))

                recv = conn.recv(RECV_BUFFER)
                message = json.loads(recv.decode('utf-8'))
                if message['type'] == 'sync_complete':
                    if message['result']:
                        print("Synced with peer {}".format(peer))
                    else:
                        print("Sync failed with peer {}".format(peer))
                        sync_fail.append(peer)
                conn.close()
            except Exception as e:
                print('sync', e)
                continue
        
        return return_to_sender


    def server_loop(self):
        try:
            while self.running:
                if self.recv_accept == True:
                    if self.server_socket is None:
                        print("Server listens on {}:{}".format(self.host, self.port))
                        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                        self.server_socket.bind((self.host, self.port))
                        self.server_socket.listen(5)
                    try:
                        self.server_socket.settimeout(1)
                        conn, addr = self.server_socket.accept()
                        threading.Thread(target=self.handle_peer_connection, args=(conn, addr)).start()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(e)
                        self.recv_accept = False
                else:
                    if self.server_socket is not None:
                        self.server_socket.close()
                        self.server_socket = None
        finally:
            if self.server_socket is not None:
                self.server_socket.close()
                self.server_socket = None
                

    def hello(self, other_port):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((self.host, other_port))
            conn.send(json.dumps({
                "type": "hello",
                "port": self.port,
                "blockchain": "None" if self.blockchain is None else self.blockchain.to_dict()
            }).encode('utf-8'))
            self.known_peers.append(other_port)
            conn.settimeout(1)
            data = conn.recv(RECV_BUFFER)
            message = json.loads(data.decode('utf-8'))
            if message['send_back']:
                self.blockchain = BlockChain()
                self.blockchain.restore(message['blockchain'])
            conn.close()
        except Exception as e:
            print('hello', e)
            


    def handle_server_commands(self):
        while self.running:
            command = input()
            if command == "exit":
                break
            if command.startswith("connect"):
                other_port = int(command.split()[1])
                self.hello(other_port)
            if command == "show":
                if self.blockchain is not None:
                    print(json.dumps(self.blockchain.to_dict(), indent=4))
                else:
                    print("Blockchain is empty")
            if command == "recv":
                if self.recv_accept:
                    print("Stopping")
                else:
                    print("Resuming")
                self.recv_accept = not self.recv_accept
            if command.startswith("produce_bad_fork"):
                miner = command.split()[1]
                self.produce_bad_fork(miner)

    def produce_bad_fork(self, miner):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((self.host, self.port))
            conn.send(json.dumps({
                "type": "produce_bad_fork",
                "miner": miner
            }).encode('utf-8'))
            data = conn.recv(RECV_BUFFER)
            message = json.loads(data.decode('utf-8'))
            if message['success']:
                print("Bad fork produced successfully")
            else:
                print("Failed to produce bad fork")
            conn.close()
        except Exception as e:
            print('produce_bad_fork', e)
    

    def run(self):
        t = threading.Thread(target=self.server_loop)
        t.start()

        self.handle_server_commands()
        
        print("Closing server")
        self.running = False
        t.join()


if __name__ == '__main__':
    host = DEFAULT_HOST
    my_port = DEFAULT_PORT
    init = False

    if len(sys.argv) >= 2:
        my_port = int(sys.argv[1])
    if len(sys.argv) == 3:
        init = True

    print(my_port)

    p2p = P2P(host, my_port, init)
    p2p.run()
