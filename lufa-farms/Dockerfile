ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
RUN apk add --no-cache python3 py3-pip

COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY run.py /app/run.py
COPY client.py /app/client.py

# Run the script
CMD [ "python3", "/app/run.py" ]
