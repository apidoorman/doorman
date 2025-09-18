# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app
COPY web-client/package.json web-client/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY web-client .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000
COPY --from=builder /app .
EXPOSE 3000
CMD ["npm", "run", "start"]

