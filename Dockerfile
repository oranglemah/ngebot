FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

COPY requirements.txt .

# Install tanpa playwright (sudah ada di base image)
RUN pip install --no-cache-dir -r requirements.txt || \
    (grep -v "playwright" requirements.txt > requirements_temp.txt && \
     pip install --no-cache-dir -r requirements_temp.txt)

RUN python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright v1.48 ready')"

COPY . .

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

CMD ["python", "k12_bot.py"]
