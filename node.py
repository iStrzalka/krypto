import socket
import threading
import sys

from defaults import *
from blockchain import BlockChain

import json

class P2P:
    def __init__(self, host, port, init):
        self.host = host
        self.port = port
        self.known_peers = []
        self.blockchain = BlockChain() if init else None
        self.wallet = None
        self.server_socket = None
        self.running = True

    def handle_peer_connection(self, conn, addr):
        try:
            message = json.loads(conn.recv(1024).decode('utf-8'))
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
                sent_to, edges = self.broadcast(message['ports_visited'], message['data'])
                if message['data']['type'] == 'new_block':
                    self.blockchain.generate_next_block(message['data'])
                conn.send(json.dumps({
                    "type": "broadcast-recv",
                    "ports_visited": sent_to,
                    "edges" : edges
                }).encode('utf-8'))    

            if message['type'] == 'ping':
                conn.send(json.dumps({
                    "type": "pong"
                }).encode('utf-8'))

            if message['type'] == 'tree':
                sent_to, edges = self.broadcast([], {"type": "tree"})
                conn.send(json.dumps({
                    "type": "tree-recv",
                    "edges" : edges,
                    "ports_visited": sent_to
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
        except:
            pass
        conn.close()


    def broadcast(self, previously_sent_to, data):
        sent_to = previously_sent_to + [self.port]
        edges = []
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
                
                recv_data = conn.recv(1024)

                message = json.loads(recv_data.decode('utf-8'))
                sent_to = message['ports_visited']
                for edge in message['edges']:
                    edges.append(edge)
                conn.close()
            except Exception as e:
                print(e)
                break
        return sent_to, edges
    
    def server_loop(self):
        print("Server listens on {}:{}".format(self.host, self.port))
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        try:
            while self.running:
                try:
                    self.server_socket.settimeout(1)
                    conn, addr = self.server_socket.accept()
                    threading.Thread(target=self.handle_peer_connection, args=(conn, addr)).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(e)
                    break
        finally:
            self.server_socket.close()

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
            data = conn.recv(1024)
            message = json.loads(data.decode('utf-8'))
            if message['send_back']:
                self.blockchain = BlockChain()
                self.blockchain.restore(message['blockchain'])
            conn.close()
        except:
            pass


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
            if command == "tree":
                self.tree()
                

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
