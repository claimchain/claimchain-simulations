# ClaimChain simulations

[![Build Status](https://travis-ci.org/claimchain/claimchain-simulations.svg?branch=master)](https://travis-ci.org/claimchain/claimchain-simulations)

This repo contains simulations for in-band public key distribution powered by ClaimChains. See the main [web page](https://claimchain.github.io) to learn about ClaimChain.

## Installation

This is based on Python 3. You will need python and the python header
files installed. On debian based systems you can achieve this with
```
apt-get install python3 python3-dev python3-pip
```

Some of the dependencies require more system packages:
```
apt-get install build-essential libssl-dev libffi-dev python3-matplotlib
```

You probably also want venv to isolate your development
environment:
```
apt-get install python3-venv
python3 -m venv venv
source venv/bin/activate
```

If you use virtualenv you need to repeat the last command every time you
want to work in the virtual env.

Now you can install the requirements:
```
pip install -r requirements.txt
```

## Download and parse the dataset

Just run ``make enron`` from the project root to download and parse the dataset to
the ``data/enron`` directory.

## Run the simulations

To run all simulations from the paper, just run ``make reports``. Mind that they
can use up to 50 GB of RAM. The simulations generate reports containing different
log information. The reports are saved to the ``data/reports`` directory.

## Open the notebooks

We use Jupyter nodebooks to compute statistics and show the plots. You can start
Jupyter with

```
upyter notebook
```

This will open a browser window, where you can select a notebook and run it.

The notebooks will save the produced plots to ``data/images`` directory.
