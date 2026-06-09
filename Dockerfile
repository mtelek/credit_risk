FROM python:3.11-slim

WORKDIR /app

RUN pip install psycopg2-binary sqlalchemy pandas

COPY src ./src
COPY sql ./sql
