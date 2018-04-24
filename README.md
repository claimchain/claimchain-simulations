# ClaimChain simulations

[![Build Status](https://travis-ci.org/claimchain/claimchain-simulations.svg?branch=master)](https://travis-ci.org/claimchain/claimchain-simulations)
[![Binder](https://mybinder.org/badge.svg)](https://mybinder.org/v2/gh/claimchain/claimchain-simulations/master?filepath=notebooks)

This repo contains simulations for in-band public key distribution powered by ClaimChains. See the main [web page](https://claimchain.github.io) to learn about ClaimChain.

## Quickstart

You can quickly launch and play around with the notebooks online using [Binder](https://mybinder.org/v2/gh/claimchain/claimchain-simulations/master?filepath=notebooks).

## Local quickstart

On a Debian-based system, you quickly setup the code and launch the notebooks
in three steps:

1. Install system and Python dependencies:
```
make deps && make venv
```

2. Download the pre-computed simulation reports and parsed dataset:
```
make data
```

3. Run the notebooks:
```
venv/bin/jupyter notebook
```

## Details

### Installation

You will need Python 3 and the Python header files installed. On Debian-based systems
you can achieve this with:
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

### Producing the data

#### Getting pre-computed data files
You can use our simulation reports, and parsed Enron dataset files, or you can
re-run them by yourself. You can download our data package from Zenodo (see 
the [data](data) folder), or run ``make data``.

#### Running simulations and parsing the dataset on your own

##### Download and parse the dataset

Just run ``make enron`` from the project root to download and parse the dataset to
the ``data/enron`` directory.

##### Run the simulations

To run all simulations from the paper, run ``make reports``. Mind that they
can use up to 50 GB of RAM. The simulations generate reports containing
different useful information. The reports are saved to the ``data/reports``
directory.


### Open the notebooks

We use Jupyter nodebooks to compute statistics and show the plots. You can
start Jupyter with ``jupyter notebook``. This will open a browser window,
where you can select a notebook and run it. The notebooks will save the
produced plots to the ``images`` directory.
