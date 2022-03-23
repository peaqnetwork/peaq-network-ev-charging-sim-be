# EV Charging Simulator

The project is split into a backend and frontend.
Please checkin the code into the appropriate folder.


## Backend Service
In current implementation

1. Users need to put the yaml file at etc/config.yaml. We have the default one, so the provider pk is //Bob//stash.
2. The uri setting applies first than mnemonic in the configuration yaml.
3. If you want to start the backend service, please run the python be.py
```
cd backend
python -m venv ~/venv.peaq
source ~/venv.peaq/bin/activate
pip3 install -r requirements.txt
python3 be.py
```
4. You can enter the website, 127.0.0.1:25566, to check socketio's information
5. When the backend service starts, you can also run the tool/user_behavior_simulation.py to simulate the user's behavior in the charging process.
6. Users can specify different configuration about consumer's pk and sudo's pk when running user_behavior_simulation.py
7. In Python 3.9, the flask-socketio is broken, so please use python 3.8 or python 3.10

## MVPv2
### How to test
There are two ways to test the charging simulator
1. Run the user simulator tools directly
In this test, the user simulator tool sends/receives the message on the Redis instead of communicating with the P2P node.
#### Environment
Remote environment
```
Peaq-node: 192.168.178.23:9944
Redis: 192.168.178.23:6379
```
Local environment
```
BE: 192.168.178.22
User simulator tool: 192.168.178.22
```
#### Steps
a. Run the peaq node on the remote server
```
cd ~/peaq-network-node
Cargo run -- --dev --tmp --ws-external
```
b. Run the redis server on the remote server
``` 
docker run --network=host redis:latest
```
c. Change the redis setting on the etc/redis.yaml on local server
```
host: "192.168.178.23"
```
d. Run the charging simulator's backend service on local server
```
python3 be.py --node_ws ws://192.168.178.23:9944
```
e. Run the user simulator tool on local server
```
python3 tool/user_behavior_simulation.py --node_ws ws://192.168.178.23:9944
```

2. Run the user simulator tools with P2P feature
In this test, we'll use the `peaq-network-ev-charging-sim-iface` and `peaq-network-ev-charging-sim-be-p2p` for the p2p communication.
#### Environment
Remote environment
```
Peaq-node: 192.168.178.23:9944
Redis: 192.168.178.23:6379
peaq-network-ev-charging-sim-be-p2p: 192.168.178.23:10333
```

Local environment
```
BE: 192.168.178.22
User simulator tool: 192.168.178.22
peaq-network-ev-charging-sim-iface: 192.168.178.22
```
#### Steps
On remote server:
a. Run the peaq node
```
cd ~/peaq-network-node
Cargo run -- --dev --tmp --ws-external
```
b. Run the redis server
``` 
docker run --network=host redis:latest
```
c. Run the p2p service
```
cd peaq-network-ev-charging-sim-be-p2p
go run ./cmd -p 10333 -sk 71b28bbd45fe04f07200190180f14ba0fe3dd903eb70b6a34ee16f9f463cfd10
```
On local server:
a. Change the redis setting on the etc/redis.yaml
```
host: "192.168.178.23"
```
b. Run the charging simulator's backend service
```
python3 be.py --node_ws ws://192.168.178.23:9944
```
c. Run the peaq-network-ev-charging-sim-iface
```
cd peaq-network-ev-charging-sim-iface
cargo run -- /ip4/192.168.178.23/tcp/10333
```
d. Run the user simulator tool
```
python3 tool/user_behavior_simulation.py --node_ws ws://192.168.178.23:9944 --p2p
```
e. Send the service request from the P2P client (peaq-network-ev-charging-sim-iface).
You should enter `ServiceRequested` on the peaq-network-ev-charging-sim-iface command line tool via the standand input.
f. Send the charging finish from the P2P client (peaq-network-ev-charging-sim-iface)
You should enter `StopCharging` on the peaq-network-ev-charging-sim-iface command line tool via the standand input.
