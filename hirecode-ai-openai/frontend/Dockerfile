FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install -g npm@11.6.3

COPY . .

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

