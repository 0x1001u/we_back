FROM python:3.9.12-alpine3.14

ENV TZ Asia/Shanghai
ENV PORT 80

RUN apk add tzdata && cp /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone \
    && apk add --no-cache ca-certificates build-base libffi-dev openssl-dev

WORKDIR /app

COPY requirements.txt .

RUN pip config set global.index-url http://mirrors.cloud.tencent.com/pypi/simple \
    && pip config set global.trusted-host mirrors.cloud.tencent.com \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

CMD ["python3", "run.py"]