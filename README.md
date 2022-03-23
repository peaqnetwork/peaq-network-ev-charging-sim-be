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
On the remote server:
a. Run the peaq node
```
cd ~/peaq-network-node
Cargo run -- --dev --tmp --ws-external
```
b. Run the redis server
``` 
docker run --network=host redis:latest
```
On the local server:
a. Change the redis setting on the etc/redis.yaml
```
host: "192.168.178.23"
```
b. Run the charging simulator's backend service
```
git submodule init
git submodule update

docker build -t be_be -f Dockerfile/Dockerfile.be .
docker run --network=host be_be
```
c. Run the user simulator tool
```
docker build -t be_user -f Dockerfile/Dockerfile.user .
docker run -it --rm --network=host be_user -ode_ws wss://wss.test.peaq.network
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
docker build -t p2p_node .
docker run -it --rm --network=host p2p_node -p 10333 -sk 71b28bbd45fe04f07200190180f14ba0fe3dd903eb70b6a34ee16f9f463cfd10
```
On local server:
a. Change the redis setting on the etc/redis.yaml
```
host: "192.168.178.23"
```
b. Run the charging simulator's backend service
```
git submodule init
git submodule update

docker build -t be_be -f Dockerfile/Dockerfile.be .
docker run --network=host be_be
```
c. Run the peaq-network-ev-charging-sim-iface
```
cd peaq-network-ev-charging-sim-iface

docker build -t sim-iface .
docker run -it --rm --network=host sim-iface /ip4/127.0.0.1/tcp/10333

or 

Follow the build script for building the peaq-node, then
docker run --rm -it -v $(pwd):/sources rust-stable:ubuntu-20.04 cargo run  --release --manifest-path=/sources/Cargo.toml -- /ip4/192.168.178.23/tcp/10333
```
d. Run the user simulator tool
```
docker build -t be_user -f Dockerfile/Dockerfile.user .
docker run -it --rm --network=host be_user -ode_ws wss://wss.test.peaq.network --p2p
```
e. Send the service request from the P2P client (peaq-network-ev-charging-sim-iface).
You should enter `ServiceRequested` on the peaq-network-ev-charging-sim-iface command line tool via the standand input.
f. Send the charging finish from the P2P client (peaq-network-ev-charging-sim-iface)
You should enter `StopCharging` on the peaq-network-ev-charging-sim-iface command line tool via the standand input.
