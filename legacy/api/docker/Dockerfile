FROM node:24

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les fichiers de dépendances
COPY package*.json ./
COPY yarn.lock ./

# Installer les dépendances
RUN yarn install

# Copier le code source
COPY . .

# Builder l'application
RUN yarn run build

EXPOSE 3000

CMD ["/bin/bash", "-c", "yarn run migration:up; yarn start:prod"]
