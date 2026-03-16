# Build frontend
FROM node:18-alpine AS build-frontend
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./

ARG VITE_S3_THEMES_BASE_URL=https://s3.timeweb.cloud/my-temp-bucket/themes/
ENV VITE_S3_THEMES_BASE_URL=$VITE_S3_THEMES_BASE_URL

RUN npm run build

# Build backend and serve
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
# Copy frontend build output to backend static directory
COPY --from=build-frontend /app/frontend/dist /app/static

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
