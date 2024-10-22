import socket
import threading
import sys

from time import sleep
from main import BlockChain, Wallet

import json

blockchain = None
known_peers = []
my_port = 5000
host = '127.0.0.1'

def broadcast(prev_sent_to, broadcast_data):
    sent_to = prev_sent_to + [my_port]
    edges = []
    for port in known_peers:
        if port in sent_to:
            continue
        edges.append((my_port, port))
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect(('127.0.0.1', port))
        sent_to.append(port)
        conn.send(json.dumps({
            "type": "broadcast",
            "data": broadcast_data,
            "already_seen_by_ports": sent_to
        }).encode('utf-8'))

        data = conn.recv(1024)

        # Zakłada że otrzyma "type" : "broadcast-recv"
        message = json.loads(data.decode('utf-8'))
        if message['type'] == 'broadcast-recv':
            sent_to = message['already_seen_by_ports']
            edges.extend(message['edges'])
        conn.close()

    return sent_to, edges
    

def handle_peer_connection(conn, addr):
    (host, port) = addr
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            # Zakłada że otrzymane dane są w formacie JSON
            # Zakłada że dane będą mniejsze niż 1024 bajty
            message = json.loads(data.decode('utf-8'))
            # print(message)
            if message['type'] == 'hello':
                # Zakłada że conajmniej jedna z dwóch stron ma blockchain
                if message['port'] not in known_peers:
                    known_peers.append(message['port'])
                global blockchain
                if blockchain is None:
                    blockchain = BlockChain()
                    blockchain.restore(message['blockchain'])
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
                        "blockchain": blockchain.to_dict()
                    }).encode('utf-8'))

            if message['type'] == 'broadcast':
                sent_to, edges = broadcast(message['already_seen_by_ports'], message['data'])
                if message['data']['type'] == 'new_block':
                    blockchain.generate_next_block(message['data'])
                conn.send(json.dumps({
                    "type": "broadcast-recv",
                    "already_seen_by_ports": sent_to,
                    "edges" : edges
                }).encode('utf-8'))    
    
        except:
            break
    conn.close()

def server_loop(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))

    server_socket.listen(5)
    while True:
        conn, addr = server_socket.accept()  
        threading.Thread(target=handle_peer_connection, args=(conn, addr)).start()

if __name__ == "__main__":
    # node port [optional start]
    my_port = int(sys.argv[1])
    if len(sys.argv) == 3:
        blockchain = BlockChain()
    
    print(f"Client P2P nasłuchuje na {host}:{my_port}")
    threading.Thread(target=server_loop, args=(host, my_port)).start()
    
    wallet = None

    while True:
        option = input("connect port/initialize( wallet)/inspect( wallet)/new( block)/exit/tree/show( entire blockchain) : ")
        if option.startswith("connect"):
            other_port = int(option.split()[1])
            if other_port not in known_peers:
                known_peers.append(other_port)
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((host, other_port))
            conn.send(json.dumps({
                "type": "hello",
                "port": my_port,
                "blockchain": "None" if blockchain is None else blockchain.to_dict()
            }).encode('utf-8'))
            data = conn.recv(1024)
            message = json.loads(data.decode('utf-8'))
            if message['send_back']:
                blockchain = BlockChain()                
                blockchain.restore(message['blockchain'])
            conn.close()
        elif option == "initialize":
            if wallet is None:
                wallet = Wallet()
                print("Portfel zainicjalizowany")
            else:
                print("Portfel już zainicjalizowany")
        elif option == "inspect":
            if wallet is not None:
                print(wallet.identity)
            else:
                print("Portfel nie został zainicjalizowany")
        elif option == "new":
            if wallet is not None:
                if blockchain is not None:
                    data = {
                        "sender": wallet.identity,
                        "receiver": "0x0",
                        "amount": 10
                    }
                    blockchain.generate_next_block(data)
                    broadcast([], {"type": "new_block", "data": data})
                else:
                    print("Brak blockchaina")
            else:
                print("Portfel nie został zainicjalizowany")
        elif option == "exit":
            break
        elif option == "tree":
            _, edges = broadcast([], {"type" : "tree"})
            print(edges)
        elif option == "show":
            if blockchain is not None:
                print(json.dumps(blockchain.to_dict(), indent=4))
        else:
            print("Nieznana komenda")
            continue
    
    sys.exit(0)

