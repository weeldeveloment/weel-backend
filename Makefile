PYTHON ?= venv/bin/python
TEST_APPS = users shared payment property stories booking notification bot sanatorium chat admin_auth
PYTHONWARNINGS ?= ignore::Warning:requests

run:
    # Run local server
	command $(PYTHON) manage.py runserver
migrate:
    # Migrate models in the database
	command $(PYTHON) manage.py makemigrations && $(PYTHON) manage.py migrate
superuser:
    # Create superuser in the database
	command $(PYTHON) manage.py createsuperuser

# --- Test DB (asosiy baza ichida test_schema, asosiy ma'lumotlarga ta'sir yo'q) ---
test-db-create:
	command $(PYTHON) manage.py create_test_db
test-db-migrate: test-db-create
	command $(PYTHON) manage.py migrate --settings=core.settings_test_db
test-db: test-db-migrate
# test_schema da testlarni ishga tushiradi
test: test-db-migrate
	command $(PYTHON) manage.py test --settings=core.settings_test_db --keepdb
# To'liq: schema + migrate + test
test-all: test

# CI/local pre-deploy automation tests (isolated, no external DB/Redis required)
test-ci:
	PYTHONWARNINGS="$(PYTHONWARNINGS)" command $(PYTHON) manage.py check --settings=core.test_settings
	PYTHONWARNINGS="$(PYTHONWARNINGS)" command $(PYTHON) manage.py test $(TEST_APPS) --settings=core.test_settings
