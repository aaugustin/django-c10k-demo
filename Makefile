test:
	python manage.py test

coverage:
	coverage erase
	coverage run --branch --source=c10kdemo,c10ktools,gameoflife manage.py test
	coverage html --omit='*/test_*.py'

clean:
	find . -name '*.pyc' -delete
	find . -name __pycache__ -delete
	rm -rf .coverage dist htmlcov MANIFEST
