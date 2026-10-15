FROM node:22-alpine
WORKDIR /app
COPY package.json server.js ./
COPY lib ./lib
COPY public ./public
RUN mkdir -p data && chown -R node:node /app
USER node
ENV PORT=3000 NODE_ENV=production
EXPOSE 3000
VOLUME ["/app/data"]
CMD ["node", "server.js"]
