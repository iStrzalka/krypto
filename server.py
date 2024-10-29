from flask import Flask, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import plotly.io as pio
import socket
from Crypto.PublicKey import RSA
import Crypto
import base64

from blockchain import Wallet

import sys
from defaults import *

import json

host = DEFAULT_HOST
RECV_BUFFER = 16384

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///krypto_wallet.db'

db = SQLAlchemy(app)

class KryptoWallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    private_key = db.Column(db.Text, nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    

def get_graph(connected_port):
    edges = []
    ports_visited = []
    for port in range(MIN_PORT, MAX_PORT + 1):
        if port in ports_visited:
            continue
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((host, port))

            conn.send(json.dumps({
                "type": "broadcast",
                "ports_visited": [],
                "data": {"type": "tree"}
            }).encode('utf-8'))

            data = conn.recv(RECV_BUFFER)

            message = json.loads(data.decode('utf-8'))

            edges += message['edges']
            if message['edges'] == []:
                edges.append([port, port])
            ports_visited += message['ports_visited']
        except Exception as e:
            continue

    G = nx.Graph()
    G.add_edges_from(edges)

    pos = nx.spring_layout(G)

    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines')

    node_x = []
    node_y = []
    for node in G.nodes():
        node_x.append(pos[node][0])
        node_y.append(pos[node][1])

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        marker=dict(
            color=[],
            size=75,
            line_width=2))

    node_text = []
    hover_text = []
    node_colors = ['lightblue'] * len(G.nodes())
    
    for node, adjacencies in enumerate(G.adjacency()):
        node_text.append('Port {}'.format(adjacencies[0]))
        hover_text.append('# of connections: '+str(len(adjacencies[1])))
        if adjacencies[0] == connected_port:
            node_colors[node] = 'lightgreen'
    
    node_trace.marker.color = node_colors
    node_trace.text = node_text
    node_trace.hovertext = hover_text

    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=0,l=0,r=0,t=0),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    )

    return fig


@app.route('/wallet', methods=['GET', 'POST'])
def wallet():
    if request.method == 'POST':
        if request.form['type'] == 'create':
            name = request.form['name']
            balance = request.form['balance']
            private_key = RSA.generate(4096, Crypto.Random.new().read)
            public_key = private_key.publickey()

            encoded_private_key = base64.b64encode(private_key.exportKey(format='DER')).decode('utf-8')
            encoded_public_key = base64.b64encode(public_key.exportKey(format='DER')).decode('utf-8')

            wallet = KryptoWallet(name=name, balance=balance, private_key=encoded_private_key, public_key=encoded_public_key)
            db.session.add(wallet)
            db.session.commit()
        if request.form['type'] == 'select':
            session['wallet'] = int(request.form['wallet'])          
        if request.form['type'] == 'send_wallet':
            if session.get('wallet', None) is not None:
                send_from = KryptoWallet.query.filter_by(id=session['wallet']).first()
                send_to = KryptoWallet.query.filter_by(id=request.form['wallet']).first()
                print(send_from, send_to)
                amount = float(request.form['amount'])
                w1, w2 = Wallet(), Wallet()
                w1.decode({'private_key': send_from.private_key, 'public_key': send_from.public_key})
                w2.decode({'private_key': send_to.private_key, 'public_key': send_to.public_key})
                signature = w1.sign(f"{send_from.public_key}{send_to.public_key}{amount}")
                
                try:
                    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    conn.connect((host, session['port']))
                    conn.send(json.dumps({
                        "type": "add_transaction",
                        "sender": w1.identity,
                        "recipient": w2.identity,
                        "amount": amount,
                        "signature": signature
                    }).encode('utf-8'))
                    data = conn.recv(RECV_BUFFER)
                    message = json.loads(data.decode('utf-8'))
                    if message['success']:
                        send_from.balance -= amount
                        send_to.balance += amount
                        db.session.commit()
                except Exception as e:
                    print(e)
                    error = "Could not send transaction"
                    return url_for("wallet", error=error)
        if request.form['type'] == 'mine':
            if session.get('wallet', None) is not None:
                miner = KryptoWallet.query.filter_by(id=session['wallet']).first()
                w = Wallet()
                w.decode({'private_key': miner.private_key, 'public_key': miner.public_key})
                try:
                    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    conn.connect((host, session['port']))
                    conn.send(json.dumps({
                        "type": "mine",
                        "miner": w.identity
                    }).encode('utf-8'))
                    data = conn.recv(RECV_BUFFER)
                    message = json.loads(data.decode('utf-8'))
                    if message['success']:
                        miner.balance += 50
                        db.session.commit()
                except Exception as e:
                    print(e)
                    error = "Could not mine"
                    return url_for("wallet", error=error)
                

    wallets = KryptoWallet.query.all()
    identities = []
    for wallet in wallets:
        w = Wallet()
        w.decode({'private_key': wallet.private_key, 'public_key': wallet.public_key})
        identities.append(w.identity)
    if session.get('wallet', None) is not None:
        wallet = KryptoWallet.query.filter_by(id=session['wallet']).first()
    else:
        wallet = -1

    transactions = []
    try:
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((host, session['port']))

        conn.send(json.dumps({
            "type": "request_blockchain_transactions"
        }).encode('utf-8'))

        data = conn.recv(RECV_BUFFER)
        
        message = json.loads(data.decode('utf-8'))
        transactions = message['transactions']
        transactions = [json.dumps(transaction, indent=4) for transaction in transactions]
    except Exception as e:
        print(e)
        error = "Could not retrieve transactions"
        return url_for("wallet", error=error)
    
    print(transactions)

    return render_template('wallet.html', wallets=wallets, active_wallet=wallet, transactions=transactions, identities=identities)


@app.route('/blockchain')
def blockchain_html():
    if 'port' not in session:
        return url_for('home', error="Please connect to a node first")
    try:
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((host, session['port']))

        conn.send(json.dumps({
            "type": "request_blockchain"
        }).encode('utf-8'))

        data = conn.recv(RECV_BUFFER)
        
        message = json.loads(data.decode('utf-8'))
        blockchain = message['blockchain']
        blockchain = [json.dumps(block, indent=4) for block in blockchain]
    except Exception as e:
        print(e)
        error = "Could not retrieve blockchain"
        return url_for("home", error=error)
    
    return render_template('blockchain.html', blockchain=blockchain)


@app.route('/', methods=['GET', 'POST'])
def home(error=None):    
    error = False if error is None else error
    if 'port' not in session:
        session['port'] = -1
    if 'wallet' not in session:
        session['wallet'] = 'None selected'
    if request.method == 'POST':
        port = request.form['port']
        
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((host, int(port)))
            conn.send(json.dumps({
                "type": "ping"
            }).encode('utf-8'))
            conn.recv(RECV_BUFFER)
            conn.close()
            session['port'] = int(port)
        except:
            error = "Invalid port or unresponsive node"
            session['port'] = -1

    fig = get_graph(session['port'])
    plot_html = pio.to_html(fig, full_html=False) 

    return render_template('index.html', plot=plot_html, error=error)

if __name__ == '__main__':
    port = 5000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    app.secret_key = 'super secret key'
    
    with app.test_request_context():
        db.create_all()
    
    app.run(port=port)