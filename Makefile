.PHONY: deps enron clean

deps:
	apt-get install python3 python3-dev python3-pip
	apt-get install build-essential libssl-dev libffi-dev python3-matplotlib

enron: Enron
	@echo "# Parsing..."
	python scripts/parse_enron.py

Enron:
	mkdir -p data/enron 
	@echo "# Downloading Enron dataset."
	@echo "# This will likely take a while..."
	wget https://www.cs.cmu.edu/~./enron/enron_mail_20150507.tar.gz -P data/enron
	@echo "Unpacking..."
	tar -xzf data/enron/enron_mail_20150507.tar.gz -C data/enron

clean:
	rm -rf data/enron
