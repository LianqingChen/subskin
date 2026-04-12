# Web Project Structure

This document describes the web/ directory structure for the SubSkin project.

## Overview

The web/ directory contains all frontend and backend components for the SubSkin website.

## Directory Structure

```
web/
├── backend/              # FastAPI backend service
│   ├── app/            # FastAPI application
│   │   └── main.py    # Main entry point with routers
│   ├── api/             # API route handlers
│   │   ├── user.py     # User authentication
│   │   ├── comment.py  # Comment management
│   │   ├── comment_admin.py  # Admin comment moderation
│   │   ├── content.py  # Content API
│   │   ├── rag.py      # RAG (Retrieval-Augmented Generation)
│   │   └── vasi.py    # VASI (Vitiligo Area Severity Index) API
│   ├── models/           # Pydantic models
│   │   ├── user.py
│   │   └── comment.py
│   ├── database/         # Database configuration
│   │   ├── database.py  # Database setup
│   │   ├── models.py    # SQLAlchemy models
│   │   └── init_db.py   # Database initialization
│   ├── services/         # Business logic
│   │   ├── auth.py      # JWT authentication
│   │   └── comment.py   # Comment service
│   ├── requirements.txt   # Python dependencies
│   ├── Dockerfile       # Container configuration
│   ├── start.sh         # Startup script
│   └── README.md        # Backend documentation
│
├── vitepress/          # VitePress frontend (static site)
│   ├── .vitepress/      # VitePress configuration
│   │   ├── config.js   # Site configuration
│   │   └── theme/     # Custom theme
│   │       ├── components/  # Vue components
│   │       └── utils/      # Utility functions
│   ├── docs/            # Markdown content
│   │   ├── index.md     # Homepage
│   │   ├── chat.html    # AI chat interface
│   │   ├── encyclopedia/  # Medical encyclopedia
│   │   ├── community/    # Community section
│   │   ├── news/        # News articles
│   │   ├── vasi/        # VASI tracking
│   │   ├── public/      # Static assets
│   │   └── weekly/      # Weekly updates
│   └── package.json     # Node.js dependencies
│
├── deploy/             # Deployment configurations
│   └── docker-compose.yml  # Docker Compose setup
│
├── public/             # Static assets (logos, images)
└── templates/           # HTML templates
```

## Backend (web/backend/)

### Technology Stack
- **Framework**: FastAPI
- **Database**: SQLite (development) / PostgreSQL (production)
- **Authentication**: JWT (JSON Web Tokens)
- **ORM**: SQLAlchemy

### API Endpoints
- `/api/user` - User registration, login, authentication
- `/api/comment` - Comment submission, retrieval
- `/api/admin/comment` - Admin comment moderation
- `/api/rag` - AI-powered Q&A with RAG
- `/api/vasi` - VASI assessment and tracking
- `/api/health` - Health check endpoint

### Environment Variables
See `web/backend/README.md` for complete configuration details.

## Frontend (web/vitepress/)

### Technology Stack
- **Framework**: VitePress (Vue 3)
- **Charts**: ECharts
- **Features**: 
  - AI chat interface
  - Encyclopedia navigation
  - Community features
  - VASI tracking system
  - Mobile-responsive design

### Content Structure
- **index.md** - Homepage with feature cards
- **encyclopedia/** - Medical knowledge base
- **community/** - Patient community features
- **news/** - Latest research updates
- **vasi/** - VASI assessment tool
- **chat.html** - AI Q&A interface

### Navigation
The site has two main navigation areas:
1. **Top Navigation** (accessed from all pages):
   - 首页
   - AI问答
   - AI病情量化
   - 病友社区

2. **Sidebar Navigation** (context-aware):
   - Community sections (about, experience, treatment, hospitals)
   - Encyclopedia categories (basic knowledge, causes, epidemiology)
   - Treatment methods
   - Latest news

## Development

### Backend Development
```bash
cd web/backend
pip install -r requirements.txt
python -m database.init_db
./start.sh
```

### Frontend Development
```bash
cd web/vitepress
npm install
npm run dev
```

### Building for Production
```bash
cd web/vitepress
npm run build
```

## Deployment

### Using Docker Compose
```bash
cd web/deploy
docker-compose up -d
```

This will start:
- PostgreSQL database
- FastAPI backend
- VitePress frontend (served as static files)

### Manual Deployment
1. **Backend**:
   - Configure environment variables
   - Run with Gunicorn or Uvicorn
   - Set up reverse proxy (Nginx)

2. **Frontend**:
   - Run `npm run build` in vitepress/
   - Serve `dist/` directory with static file server
   - Configure domain and SSL

## Integration Points

### Backend ↔ Frontend Communication
1. **AI Chat**: Frontend sends questions to `/api/rag/chat`
2. **Comments**: Frontend posts to `/api/comment/submit`
3. **VASI**: Frontend submits images to `/api/vasi/assess`
4. **Authentication**: JWT tokens stored in localStorage, sent with API requests

### Backend ↔ Python Core
- Backend can import and use `src/models/` (Paper, ClinicalTrial)
- Backend can access `data/` exports for API responses
- RAG uses `src/processors/` for AI processing

## Notes

- **No web/web directory**: This was removed as it was a duplicate of web/vitepress
- **Separate concerns**: Backend (API) and frontend (static site) are cleanly separated
- **Database isolation**: Backend has its own database, not shared with crawler database
- **Static assets**: Logos and images in `web/public/` are shared by both frontend and backend
