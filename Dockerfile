FROM node:20-slim AS web
WORKDIR /web
COPY app/web/package.json app/web/package-lock.json* ./
RUN npm install
COPY app/web .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY --from=web /web/dist ./app/web/dist
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
