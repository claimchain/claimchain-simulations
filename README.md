# ClaimChain simulations

See the main ClaimChain repo [here](https://github.com/claimchain/claimchain-core).

## Installation

This is based on Python 3. You will need python and the python header
files installed. On debian based systems you can achieve this with
```
  apt-get install python3 python3-dev python3-pip
```

Some of the dependencies require more system packages:
```
  apt-get install libssl-dev libffi-dev python3-matplotlib
```

You probably also want virtualenv to isolate your development
environment:
```
  apt-get install virtualenv
  virtualenv -p python3 venv
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
the _Enron_ directory.

## Opening the Notebooks

We use Jupyter nodebooks to run the simulations. You can start Jupyter
with
  jupyter

In the browser window that opens you can then open the notebook in
question and run it.

## Making the notebooks work...

The `run_scenarios` notebook expects a reports directory to exist inside
the notebooks folder.

Currently the code to compute new reports is commented out in the
notebook and instead it tries to load reports stored on disk.
In order to start from scratch you will have to uncomment the lines
following
```
# Compute new reports
```

## Running notebooks on the command line

You can use runipy to run a given notebook from the command line:
```
  pip install runipy
  runipy notebooks/run_scenarios.ipynb
```
