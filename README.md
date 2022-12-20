# EV Charging Simulator

The project is split into a backend and frontend.
Please checkin the code into the appropriate folder.


## Mnemonic
Currently, because of security, users need to assign the mnemonic at their environemnt varialbes, PROVIDER_MNEMONIC and CONSUMER_MNEMONIC. Users can also use the PROVIDER_URI and CONSUMER_URI to apply for the development. They URI has higher prority than MNEMONIC. Besides, due to avoiding the limitation of deployment environment, please use double quote on the environment variable.
For example: PROVIDER_MNEMONIC="word1 word2 word3 word4"

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
4. You can enter the website, 127.0.0.1:25566, to check socketio's information.
5. When the backend service starts, you can also run the tool/user_behavior_simulation.py to simulate the user's behavior in the charging process.
6. Users can specify different configuration about consumer's pk and sudo's pk when running user_behavior_simulation.py
7. In Python 3.9, the flask-socketio is broken, so please use python 3.8 or python 3.10

## MVPv2
### How to test
There are two ways to test the charging simulator

#### Run the user simulator tools directly
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
1. Run the peaq node
```
cd ~/peaq-network-node
Cargo run -- --dev --tmp --ws-external
```
2. Run the redis server
``` 
docker run --network=host redis:latest
```
On the local server:

1. Change the redis setting on the etc/redis.yaml
```
host: "192.168.178.23"
```
2. Run the charging simulator's backend service
```
git submodule init
git submodule update

docker build -t be_be -f Dockerfile .
docker run --network=host be_be
```
3. Run the user simulator tool
```
docker build -t be_user -f tool/Dockerfile.user .
docker run -it --rm --network=host be_user --node_ws wss://wss.test.peaq.network
```


#### Run the user simulator tools with P2P feature
In this test, we'll use the `peaq-network-ev-charging-sim-iface` and `peaq-network-ev-charging-sim-be-p2p` for the p2p communication.


##### Environment
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
##### Steps
On remote server:

1. Run the peaq node
```
cd ~/peaq-network-node
Cargo run -- --dev --tmp --ws-external
```
2. Run the redis server
``` 
docker run --network=host redis:latest
```
3. Run the p2p service
```
cd peaq-network-ev-charging-sim-be-p2p
docker build -t p2p_node .
docker run -it --rm --network=host p2p_node -p 10333 -sk 71b28bbd45fe04f07200190180f14ba0fe3dd903eb70b6a34ee16f9f463cfd10
```

On local server:
1. Change the redis setting on the etc/redis.yaml
```
host: "192.168.178.23"
```
2. Run the charging simulator's backend service
```
git submodule init
git submodule update

docker build -t be_be -f Dockerfile .
docker run --network=host be_be
```
3. Run the peaq-network-ev-charging-sim-iface
```
cd peaq-network-ev-charging-sim-iface

docker build -t sim-iface .
docker run -it --rm --network=host sim-iface /ip4/192.168.178.23/tcp/10333

or 

Follow the build script for building the peaq-node, then
docker run --rm -it -v $(pwd):/sources rust-stable:ubuntu-20.04 cargo run  --release --manifest-path=/sources/Cargo.toml -- /ip4/192.168.178.23/tcp/10333
```
4. Run the user simulator tool
```
docker build -t be_user -f tool/Dockerfile.user .
docker run -it --rm --network=host be_user --node_ws wss://wss.test.peaq.network --p2p
```
5. Send the service request from the P2P client (peaq-network-ev-charging-sim-iface).
You should enter `ServiceRequested` on the peaq-network-ev-charging-sim-iface command line tool via the standand input.
6. Send the charging finish from the P2P client (peaq-network-ev-charging-sim-iface)
You should enter `StopCharging` on the peaq-network-ev-charging-sim-iface command line tool via the standand input.
