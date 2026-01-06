FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

COPY requirements.txt .

# Install Playwright Python package
RUN pip install --no-cache-dir -r requirements.txt

# Verify
RUN python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright v1.48 ready')"

COPY . .

# Use pre-installed browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

CMD ["python", "k12_bot.py"]
