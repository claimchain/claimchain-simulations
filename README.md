# ClaimChain simulations

[![Build Status](https://travis-ci.org/claimchain/claimchain-simulations.svg?branch=master)](https://travis-ci.org/claimchain/claimchain-simulations)
[![Binder](https://mybinder.org/badge.svg)](https://mybinder.org/v2/gh/claimchain/claimchain-simulations/master?filepath=notebooks)

This repo contains simulations of in-band public key distribution for messaging
using ClaimChains. See the main [web page](https://claimchain.github.io) to
learn about the ClaimChain data structure.

## Quickstart with Binder
You can launch and run the notebooks *online* using [Binder](https://mybinder.org/v2/gh/claimchain/claimchain-simulations/master?filepath=notebooks)
without the need to install anything locally.

## Local quickstart
On a Debian-based system, you can set up the code and launch the notebooks
in three steps:

1. Install system and Python dependencies:
```
make deps && make venv
```

2. Download the pre-computed simulation reports and the processed dataset:
```
make data
```

3. Run the notebooks:
```
venv/bin/jupyter notebook notebooks
```

The last command will open browser window with [Jupyter](https://jupyter.org/)
running.


## Details

### Installation
You will need Python 3 and the Python header files installed. On Debian-based
systems you can achieve this with:
```
apt-get install python3 python3-dev python3-pip
```

Some of the dependencies require more system packages:
```
apt-get install build-essential libssl-dev libffi-dev python3-matplotlib
```

You probably also want venv to isolate your development environment:
```
apt-get install python3-venv
python3 -m venv venv
source venv/bin/activate
```

If you use virtualenv you need to repeat the last command every time you
want to work in the virtual environment.

Now you can install the requirements:
```
pip install -r requirements.txt
```

All of these can also be done by running ``make deps && make venv``.


### Producing the data

#### Getting pre-computed data files
You can either use the simulation reports and pre-processed Enron dataset
files that we have produced, or you reproduce them yourself. You can download
our data package from Zenodo (see the [data](data) folder), or by running
``make data``.

#### Running simulations and parsing the dataset on your own

##### Download and process the dataset
The simulations use the [Enron dataset](https://www.cs.cmu.edu/~./enron/) as
the test load. Run ``make enron`` from the project root to download and process
the dataset to the ``data/enron/parsed`` directory.

##### Run the simulations
To run the simulations from the paper, run ``make reports``. Mind that they
can use up to 50 GB of RAM, and take upwards of 25 hours on an Intel Xeon E5
machine. The simulations generate reports containing various useful
information, and are saved to the ``data/reports`` directory.


### Opening the notebooks
We use Jupyter nodebooks to compute statistics and show the plots. You can
start Jupyter with ``jupyter notebook``. This will open a browser window,
where you can select a notebook from the [notebooks](notebooks) directory 
and run it. The notebooks will save all produced plots to the ``images``
directory.


## Acknowledgements

This work is funded by the [NEXTLEAP project](https://nextleap.eu) within the
European Union’s Horizon 2020 Framework Programme for Research and Innovation
(H2020-ICT-2015, ICT-10-2015) under grant agreement 688722.

