FROM python:3.12-slim

# opencv-python-headless 仍會連結 libglib2.0,所以還是要裝這一個系統套件;
# OCR 用 ONNX Runtime(CPU),不需要 CUDA 映像
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MAX_UPLOAD_MB=100 \
    PORT=8000

RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# OCR 點陣化解析度;150 快約 4 成,200 準確度較好,再高對這個模型沒有幫助
ENV OCR_DPI=200

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py convert_core.py batch_convert.py ./
COPY static ./static

# 非 root 使用者
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health').read()" || exit 1

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
