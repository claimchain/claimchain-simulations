.PHONY: data deps enron reports clean

deps:
	apt-get install python3 python3-dev python3-pip
	apt-get install build-essential libssl-dev libffi-dev python3-matplotlib parallel

data:
	@echo "# Downloading pre-computed reports and parsed dataset files."
	@mkdir -p .tmp
	wget https://zenodo.org/record/1228178/files/data.tar.gz -P .tmp
	@echo "Unpacking..."
	tar -xzf .tmp/data.tar.gz -C data

enron: data/enron
	@echo "# Parsing..."
	PYTHONPATH=. ./scripts/parse_enron.py

data/enron:
	@mkdir -p data/enron 
	@mkdir -p .tmp
	@echo "# Downloading Enron dataset."
	@echo "# This will likely take a while..."
	wget https://www.cs.cmu.edu/~./enron/enron_mail_20150507.tar.gz -P .tmp
	@echo "Unpacking..."
	tar -xzf .tmp/enron_mail_20150507.tar.gz -C data/enron

reports:
	mkdir -p data/reports
	PYTHONPATH=. ./scripts/generate_reports.sh

clean:
	rm -rf .tmp
