ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies based on Alpine
# ttyd is often in community or edge/community repo
RUN apk add --no-cache \
    python3 \
    py3-pip \
    nodejs \
    npm \
    ttyd \
    git \
    bash \
    curl \
    nano

# Install Google Gemini CLI globally
RUN npm install -g @google/gemini-cli

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
