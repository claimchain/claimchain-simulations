.PHONY: enron clean

enron: Enron
	@echo "# Parsing..."
	python scripts/parse_enron.py

Enron:
	mkdir -p Enron
	@echo "# Downloading Enron dataset."
	@echo "# This will likely take a while..."
	wget https://www.cs.cmu.edu/~./enron/enron_mail_20150507.tar.gz -P Enron
	@echo "Unpacking..."
	tar -xzf Enron/enron_mail_20150507.tar.gz -C Enron

clean:
	rm -rf Enron
