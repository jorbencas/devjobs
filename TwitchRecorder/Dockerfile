FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl unzip && \
    # Install deno in user-accessible location
    mkdir -p /home/appuser/.deno/bin && \
    curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/home/appuser/.deno sh && \
    ln -sf /home/appuser/.deno/bin/deno /usr/local/bin/deno && \
    chown -R 1000:1000 /home/appuser && \
    rm -rf /var/lib/apt/lists/*

# Ensure PATH includes deno
ENV PATH="/home/appuser/.deno/bin:/usr/local/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /recordings && chown 1000:1000 /recordings

# Ensure appuser owns the app directory
RUN chown -R 1000:1000 /app

USER 1000:1000

ENTRYPOINT ["python", "-u", "main.py"]
CMD []