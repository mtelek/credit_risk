FROM python:3.11-slim

WORKDIR /app

RUN pip install psycopg2-binary sqlalchemy pandas kaggle scorecardpy

COPY src ./src
COPY sql ./sql
