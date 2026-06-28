FROM python:3.11-slim

WORKDIR /app

RUN pip install psycopg2-binary sqlalchemy "pandas<2.2" kaggle scorecardpy

COPY src ./src
COPY sql ./sql
