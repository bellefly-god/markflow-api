# MarkFlow API - OpenRouter Integration

This guide explains how to deploy MarkFlow API and expose it on OpenRouter for monetization.

## OpenRouter Model Configuration

To list MarkFlow on OpenRouter, you need to provide the following configuration:

### Model Schema

```json
{
  "id": "markflow/markflow-convert",
  "name": "MarkFlow Document Converter",
  "description": "Convert any document (PDF, DOCX, PPTX, XLSX) to clean Markdown for LLMs",
  "context_length": 128000,
  "pricing": {
    "prompt": "0.000001",
    "completion": "0.000002"
  },
  "architecture": {
    "modality": "text->text",
    "tokenizer": "GPT",
    "instruct_type": null
  },
  "top_provider": {
    "context_length": 128000,
    "max_completion_tokens": 32000,
    "is_moderated": false
  },
  "per_request_limits": {
    "prompt_tokens": 100000,
    "completion_tokens": 32000
  }
}
```

### Available Models

| Model ID | Description | Use Case |
|----------|-------------|----------|
| `markflow/markflow-convert` | Document to Markdown conversion | Convert PDF/DOCX/PPTX/XLSX to Markdown |
| `markflow/markflow-summarize` | AI-powered summarization | Generate summaries, key points, tags |
| `markflow/markflow-full` | Convert + Summarize | Full pipeline in one call |

## API Endpoints

### OpenAI-Compatible Endpoints

```
POST /v1/chat/completions
GET /v1/models
```

### Usage Examples

#### Using OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-markflow-api.com/v1",
    api_key="your-api-key"
)

# Convert document
response = client.chat.completions.create(
    model="markflow-convert",
    messages=[{
        "role": "user",
        "content": "Convert this document to Markdown..."
    }]
)

# Summarize
response = client.chat.completions.create(
    model="markflow-summarize",
    messages=[{
        "role": "user", 
        "content": markdown_content
    }]
)
```

#### Using curl

```bash
# Convert document
curl -X POST https://your-api.com/v1/convert \
  -H "X-API-Key: your-key" \
  -F "file=@document.pdf"

# Chat completion
curl -X POST https://your-api.com/v1/chat/completions \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "markflow-summarize",
    "messages": [{"role": "user", "content": "Your markdown content"}]
  }'
```

## OpenRouter Integration Steps

### 1. Deploy the API

```bash
# Using Docker
docker-compose up -d

# Or directly
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Set up Public URL

Use one of these options:
- **Cloudflare Tunnel** (recommended, free)
- **Ngrok** for testing
- **AWS/GCP/Azure** with load balancer
- **Railway/Render/Fly.io** for easy deployment

### 3. Register on OpenRouter

1. Go to https://openrouter.ai/
2. Create a provider account
3. Submit your API endpoint:
   - Base URL: `https://your-domain.com/v1`
   - Models: `markflow-convert`, `markflow-summarize`, `markflow-full`
   - Authentication: API Key header

### 4. Pricing Configuration

Set your pricing on OpenRouter dashboard:

| Model | Input (per 1K tokens) | Output (per 1K tokens) |
|-------|----------------------|------------------------|
| markflow-convert | $0.001 | $0.002 |
| markflow-summarize | $0.002 | $0.004 |
| markflow-full | $0.003 | $0.006 |

## Revenue Model

### Pricing Suggestions

| Tier | Price | Requests/month | Features |
|------|-------|----------------|----------|
| Free | $0 | 100 | Basic conversion, 5MB limit |
| Pro | $9/mo | 1,000 | AI summary, 50MB, priority |
| Business | $49/mo | 10,000 | All features, 100MB, SLA |
| Enterprise | Custom | Unlimited | Self-hosted, support |

### Estimated Revenue

- 1000 users × $9 = $9,000/month
- 100 business users × $49 = $4,900/month
- API usage fees from OpenRouter

## Monitoring

### Prometheus Metrics

Access metrics at `http://localhost:9090/metrics`

Key metrics:
- `markflow_conversions_total`
- `markflow_tokens_used_total`
- `markflow_conversion_duration_seconds`
- `markflow_errors_total`

### Grafana Dashboard

Import the provided dashboard in `grafana-dashboard.json`
