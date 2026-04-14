FROM node:22-alpine

WORKDIR /app

# Install dependencies into the image layer. The host node_modules is
# shadowed by the frontend_node_modules named volume in compose.yaml so
# that Alpine-native binaries (esbuild, rollup) are used at runtime.
COPY frontend/package*.json ./
RUN npm ci

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
