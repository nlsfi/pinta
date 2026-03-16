# Processing component

Running Python code from processing component:

* Build the container in project root: `docker-compose build processing`
* Run code: `docker-compose run --rm processing python -m pinta_processing.main` or `docker-compose run --rm processing python src/pinta_processing/main.py`
