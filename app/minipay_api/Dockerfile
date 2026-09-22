FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/minipay_api

# Run as non-root
RUN useradd -m minipay
USER minipay

EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8080/health', timeout=2).status==200 else sys.exit(1)"

CMD ["uvicorn", "minipay_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
