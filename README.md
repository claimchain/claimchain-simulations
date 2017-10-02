# ClaimChain simulations

Here be dragons.

These will be cleaned up and fixed eventually.


## Installation

This is based on python 3. You will need python and the python header
files installed. On debian based systems you can achieve this with
```
  apt install python3 python3-dev python3-pip
```

You probably also want virtualenv to isolate your development
environment:
```
  apt install python3-venv
  pyvenv venv
  source venv/bin/activate
```

If you use virtualenv you need to repeat the last command every time you
want to work in the virtual env.

Now you can install the requirements:
```
  pip install -r requirements.txt
```

## Download the Dataset

https://www.cs.cmu.edu/~enron/ provides the Enron email dataset as a
gzipped tarball.

This package contains a directory called maildir that our scripts expect
to reside in an Enron subdirectory. This should get you setup:;

```
  mkdir Enron
  cd Enron
  wget https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
  tar -xzvf enron_mail_20150507.tar.gz
```

## Parse the Dataset

```
python scripts/parse_enron.py
```

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
