.PHONY: deps enron reports clean

deps:
	apt-get install python3 python3-dev python3-pip
	apt-get install build-essential libssl-dev libffi-dev python3-matplotlib parallel

enron: data/enron
	@echo "# Parsing..."
	PYTHONPATH=. ./scripts/parse_enron.py

data/enron:
	mkdir -p data/enron 
	@echo "# Downloading Enron dataset."
	@echo "# This will likely take a while..."
	wget https://www.cs.cmu.edu/~./enron/enron_mail_20150507.tar.gz -P data/enron
	@echo "Unpacking..."
	tar -xzf data/enron/enron_mail_20150507.tar.gz -C data/enron

reports:
	mkdir -p data/reports
	PYTHONPATH=. ./scripts/generate_reports.sh

clean:
	rm -rf data/enron
