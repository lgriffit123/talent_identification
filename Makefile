install:
	python3 -m pip install --upgrade pip
	python3 -m pip install -r requirements.txt

test:
	python3 -m pytest -q

run:
	python3 main.py

setup: install 