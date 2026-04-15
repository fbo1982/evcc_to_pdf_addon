ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-pandas \
    py3-jinja2 \
    py3-requests \
    py3-brotli \
    pango \
    harfbuzz \
    fontconfig \
    ttf-dejavu \
    ttf-liberation

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt --break-system-packages || \
    pip3 install --no-cache-dir -r /app/requirements.txt

COPY generate_pdf_report.py /app/
COPY template_de.html /app/
COPY template_en.html /app/
COPY run.sh /run.sh

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
