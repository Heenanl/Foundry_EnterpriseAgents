FROM mcr.microsoft.com/devcontainers/python:3.12

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 3978
CMD ["python", "app.py"]
