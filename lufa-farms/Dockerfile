ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
RUN apk add --no-cache python3 py3-requests py3-beautifulsoup4

WORKDIR /app
COPY run.py /app/run.py
COPY client.py /app/client.py

# Run the script
CMD [ "python3", "/app/run.py" ]
