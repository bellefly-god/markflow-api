# MarkFlow API

将文档转换为 Markdown 的 API 服务，支持 AI 摘要功能，可部署在 OpenRouter 上售卖。

## 功能特性

- **多格式支持**: PDF, DOCX, PPTX, XLSX, HTML, 图片, 音频等
- **AI 摘要**: 自动生成文档摘要、关键点、标签
- **OpenAI 兼容**: 可通过 OpenAI SDK 直接调用
- **OpenRouter 就绪**: 专为 API 变现设计

## 快速开始

### 1. 安装依赖

```bash
# 使用 Python 3.11+
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 到 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env`:
```env
OPENAI_API_KEY=your-openai-api-key
SECRET_KEY=your-secret-key
```

### 3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

或使用启动脚本：
```bash
chmod +x start.sh
./start.sh
```

## API 端点

### 文档转换

```bash
# 转换文档
curl -X POST http://localhost:8000/v1/convert \
  -H "X-API-Key: mf_demo_key_for_testing" \
  -F "file=@document.pdf"
```

### AI 摘要

```bash
# 生成摘要
curl -X POST http://localhost:8000/v1/summarize \
  -H "X-API-Key: mf_demo_key_for_testing" \
  -F "content=# Document content..."
```

### 一键转换+摘要

```bash
curl -X POST http://localhost:8000/v1/convert-and-summarize \
  -H "X-API-Key: mf_demo_key_for_testing" \
  -F "file=@document.pdf"
```

### OpenAI 兼容接口

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mf_demo_key_for_testing"
)

# 摘要
response = client.chat.completions.create(
    model="markflow-summarize",
    messages=[{"role": "user", "content": "# Your markdown content..."}]
)
```

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/v1/docs
- ReDoc: http://localhost:8000/v1/redoc

## Docker 部署

```bash
# 构建镜像
docker build -t markflow-api .

# 运行容器
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  -v ./uploads:/app/uploads \
  markflow-api
```

或使用 docker-compose:
```bash
docker-compose up -d
```

## 支持的文件格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| PDF | .pdf | 便携文档格式 |
| Word | .docx | Microsoft Word |
| PowerPoint | .pptx | Microsoft PowerPoint |
| Excel | .xlsx, .xls | Microsoft Excel |
| HTML | .html, .htm | 网页 |
| 图片 | .png, .jpg, .gif | 支持 OCR |
| 音频 | .mp3, .wav | 支持语音转文字 |
| 数据 | .csv, .json, .xml | 结构化数据 |
| 电子书 | .epub | EPUB 格式 |

## 项目结构

```
markflow-api/
├── app/
│   ├── main.py          # FastAPI 应用入口
│   ├── api/
│   │   └── routes.py    # API 路由
│   ├── core/
│   │   ├── config.py    # 配置管理
│   │   └── security.py  # 安全工具
│   ├── models/
│   │   └── schemas.py   # Pydantic 模型
│   └── services/
│       └── converter.py # 文档转换服务
├── uploads/             # 上传文件目录
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## OpenRouter 变现

详见 [OPENROUTER.md](./OPENROUTER.md)

## License

MIT
