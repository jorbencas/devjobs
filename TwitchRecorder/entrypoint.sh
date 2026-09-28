#!/bin/bash
echo "Container TZ:"
cat /etc/timezone 2>/dev/null || echo 'no /etc/timezone'
echo "date:"
date
echo "TZ env:"
echo $TZ
python -c "import datetime; print('Python datetime.now():', datetime.datetime.now()); print('Python datetime.utcnow():', datetime.datetime.utcnow())"
exec python -u main.py
