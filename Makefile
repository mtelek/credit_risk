COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

start:
	$(COMPOSE) up --build

up:
	$(COMPOSE) up

download-data:
	$(COMPOSE) run --rm --build app python src/download_kaggle.py

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v
	rm -fr data/
