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
