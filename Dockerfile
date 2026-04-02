FROM python:3.10-slim

WORKDIR /app

COPY . /app

# Set container timezone (can be overridden at runtime with -e TZ=...).
ENV TZ=Asia/Kolkata
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
	&& ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
	&& echo $TZ > /etc/timezone \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers + dependencies
RUN pip install playwright
RUN playwright install --with-deps

CMD ["sh", "-c", "while true; do python updated_version_script.py; sleep 300; done"]