start:
	docker compose up --build -d

up:
	docker compose up -d

download-data:
	docker compose run --rm --build app python src/download_kaggle.py

down:
	docker compose down

clean:
	docker compose down -v
