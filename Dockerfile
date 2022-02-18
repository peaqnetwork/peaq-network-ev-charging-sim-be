FROM rust:1.57-bullseye as rustcompiler

RUN DEBIAN_FRONTEND=NONITERACTIVE && \
    apt update && \
    apt install -y python3 python3-pip

ADD . /peaq/simulator/

WORKDIR /peaq/simulator

RUN pip3 install -r requirements.txt

FROM python:3.9-bullseye

COPY --from=rustcompiler /peaq/simulator /peaq/simulator
COPY --from=rustcompiler /usr/local/lib/python3.9/dist-packages/ /usr/local/lib/python3.9/dist-packages/

WORKDIR /peaq/simulator
RUN pip3 install -r requirements.txt

EXPOSE 25566

CMD [ "python3", "/peaq/simulator/be.py", "--node_ws", "wss://wss.test.peaq.network", "--url", "0.0.0.0"]
