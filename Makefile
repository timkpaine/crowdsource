server:  ## run server
	python3 -m crowdsource.server --debug

questions:  ## run example questions
	python3 examples/local/sample_questions.py

answers:  ## run example answers
	python3 examples/local/sample_answers.py

bonds:  ## run bonds example
	python3 examples/competitions/corporate_bonds.py

tests: ## Clean and Make unit tests
	CROWDSOURCE_KEY=TEST CROWDSOURCE_SECRET=TEST python3 -m pytest -vvv crowdsource/tests/ --cov=crowdsource

annotate: ## MyPy type annotation check
	mypy -s crowdsource  

annotate_l: ## MyPy type annotation check - count only
	mypy -s crowdsource | wc -l 

lint: ## run linter
	flake8 crowdsource
	yarn lint

fix:  ## run autopep8/tslint fix
	autopep8 --in-place -r -a -a crowdsource/
	./node_modules/.bin/tslint --fix src/ts/**/*.ts

js:  ## build the js
	yarn
	yarn build

fixtures:  ## make db fixtures
	python3 -m crowdsource.persistence.fixtures sqlite:///crowdsource.db

# db:  ## Remake the db
# 	echo crowdsource > tmppw
# 	initdb -D db/ -A md5  -U cs --pwfile=tmppw
# 	rm tmppw
# 	sed -i -le 's/\#port\ \=\ 5432/port\ \=\ 8890/' db/postgresql.conf
# 	pg_ctl -D db -l logfile start
# 	createdb -O cs cs -E utf-8 -U cs -p 8890

# migrations:  ## apply migrations to the db
# 	python3 crowdsource/persistence/migrations/0001.py
# 	python3 crowdsource/persistence/migrations/0002.py

clean: ## clean the repository
	find . -name "__pycache__" | xargs  rm -rf
	rm -rf .pytest_cache 
	find . -name "*.pyc" | xargs rm -rf 
	rm -rf .coverage cover htmlcov logs build dist *.egg-info
	make -C ./docs clean

example: ## run simple example
	python3 crowdsource/example.py

build:  ## build the repository
	python3 setup.py build

install:  ## install to site-packages
	python3 setup.py install

docs:  ## make documentation
	make -C ./docs html && open docs/_build/html/index.html

dist:  ## dist to pypi
	rm -rf dist build
	python3 setup.py sdist
	python3 setup.py bdist_wheel
	twine check dist/* && twine upload dist/*


# Thanks to Francoise at marmelab.com for this
.DEFAULT_GOAL := help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

print-%:
	@echo '$*=$($*)'

.PHONY: clean run test tests help annotate annotate_l docs server sqlserver questions answers  db migrations
