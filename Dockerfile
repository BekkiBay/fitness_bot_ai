FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install -U pip && pip install -e .

COPY . .

CMD ["python", "-m", "bukafit.bot.main"]
