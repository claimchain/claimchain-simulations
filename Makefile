.PHONY: deps venv data clean
.PHONY: enron reports

deps:
	apt-get install python3 python3-dev python3-pip python3-venv
	apt-get install build-essential libssl-dev libffi-dev python3-matplotlib parallel

venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt

data:
	@echo "# Downloading pre-computed reports and parsed dataset files."
	@mkdir -p .tmp
	wget https://zenodo.org/record/1228178/files/data.tar.gz -P .tmp
	@echo "Unpacking..."
	tar -xzf .tmp/data.tar.gz -C data

enron: data/enron
	@echo "# Parsing..."
	PYTHONPATH=. venv/bin/python ./scripts/parse_enron.py

data/enron:
	@mkdir -p data/enron 
	@mkdir -p .tmp
	@echo "# Downloading Enron dataset."
	@echo "# This will likely take a while..."
	wget https://www.cs.cmu.edu/~./enron/enron_mail_20150507.tar.gz -P .tmp
	@echo "Unpacking..."
	tar -xzf .tmp/enron_mail_20150507.tar.gz -C data/enron

reports:
	@mkdir -p data/reports
	PYTHONPATH=. PYTHON=venv/bin/python ./scripts/generate_reports.sh

clean:
	rm -rf .tmp
