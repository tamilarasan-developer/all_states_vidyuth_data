FROM python:3.10-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers + dependencies
RUN pip install playwright
RUN playwright install --with-deps

CMD ["sh", "-c", "while true; do python updated_version_script.py; sleep 300; done"]