.PHONY: install run list batch dashboard clean

install:
	pip install -r requirements.txt

list:
	python pipeline.py --list

run:
	python pipeline.py --index $(INDEX)

batch:
	python pipeline.py --batch --max $(MAX)

dashboard:
	streamlit run app.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
