# Use Python 3.10 slim image
FROM python:3.10-slim

# Install Chrome, ChromeDriver and dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromium

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY main.py .

# Set environment variables for Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONUNBUFFERED=1

# Make sure ChromeDriver is in PATH
ENV PATH="/usr/bin:${PATH}"

# Run the application
CMD exec functions-framework --target=check_shirakawago_availability --port=$PORT