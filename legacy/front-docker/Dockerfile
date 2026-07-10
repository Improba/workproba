
FROM node:24-alpine

RUN mkdir /app
WORKDIR /app
COPY package*.json ./
COPY yarn.lock ./
RUN yarn install
COPY . .

RUN ./node_modules/.bin/quasar build -m spa

RUN apk add --update nginx

RUN mkdir -p /usr/share/nginx/html
RUN cp ./nginx/default.conf /etc/nginx/http.d/default.conf
RUN cp -rf ./dist/spa/* /usr/share/nginx/html

EXPOSE 80
CMD ["nginx","-g","pid /tmp/nginx.pid; daemon off;"]
