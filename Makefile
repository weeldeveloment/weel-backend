run:
    # Run local server
	command python3 manage.py runserver
migrate:
    # Migrate models in the database
	command python3 manage.py makemigrations && python3 manage.py migrate
superuser:
    # Create superuser in the database
	command python3 manage.py createsuperuser

# --- Test DB (asosiy baza ichida test_schema, asosiy ma'lumotlarga ta'sir yo'q) ---
test-db-create:
	command python3 manage.py create_test_db
test-db-migrate: test-db-create
	command python3 manage.py migrate --settings=core.settings_test_db
test-db: test-db-migrate
# test_schema da testlarni ishga tushiradi
test: test-db-migrate
	command python3 manage.py test --settings=core.settings_test_db --keepdb
# To'liq: schema + migrate + test
test-all: test