FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    pymupdf \
    rich \
    inquirerpy \
    tqdm \
    readchar \
    pikepdf \
    Pillow

COPY desproteger_pdf.py .

RUN mkdir -p pdfs_protegidos pdfs_libres

CMD ["python", "-u", "desproteger_pdf.py"]
