FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY channelscout ./channelscout
RUN pip install --no-cache-dir --no-deps .
COPY tests ./tests
COPY scripts ./scripts
COPY evaluation ./evaluation
RUN useradd --create-home scout
USER scout
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "channelscout.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "info"]
