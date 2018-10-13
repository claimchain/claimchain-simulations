FROM ubuntu:18.04

# Create user with a home directory
ARG NB_USER
ARG NB_UID
ENV USER ${NB_USER}
ENV HOME /home/${NB_USER}
ENV DEBIAN_FRONTEND noninteractive

RUN adduser --disabled-password \
    --gecos "Default user" \
    --uid ${NB_UID} \
    ${NB_USER}
WORKDIR ${HOME}

RUN apt-get update -qq
RUN apt-get install -y build-essential -qq

COPY . ${HOME}
RUN make deps
RUN make data > /dev/null 2>&1
RUN pip3 install -qq --no-cache --upgrade pip
RUN pip3 install -qq -r requirements.txt

CMD ["jupyter", "notebook", "--ip", "0.0.0.0"]
