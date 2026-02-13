# Raxy Farm

A comprehensive automation and management platform for Microsoft Rewards accounts, designed with enterprise-grade architecture and modern development practices.

## Overview

Raxy Farm is a full-stack application that automates Microsoft Rewards point farming across multiple accounts. The system consists of a robust Python backend handling automation logic and a modern React dashboard for monitoring, management, and operations.

Built for scalability and reliability, the platform supports both file-based and database-driven account management, parallel execution, intelligent proxy rotation, and real-time monitoring capabilities.

---

## Key Features

### Backend Automation Engine

**Batch Processing**  
Execute farming operations across multiple accounts simultaneously using `ThreadPoolExecutor`, dramatically reducing total processing time while respecting rate limits and system resources.

**Intelligent Proxy Management**  
Seamless integration with Xray/V2Ray proxies for connection routing. The system automatically tests proxy health, rotates connections, and manages proxy pools to ensure consistent account access without geographic restrictions.

**Flexible Data Sources**  
Dual-mode account management supporting both traditional file-based configuration (`users.txt`) and modern cloud database storage via Supabase. Switch between sources dynamically based on operational needs.

**Clean Architecture**  
Enterprise-grade codebase structured around SOLID principles with dependency injection, clear separation of concerns between domain entities, services, repositories, and API clients. The modular design ensures maintainability and testability.

**RESTful API**  
Comprehensive FastAPI implementation exposing all backend functionality through well-documented HTTP endpoints at `/api/v1`. Enables integration with the dashboard, CLI tools, or third-party applications.

**Powerful CLI Interface**  
Feature-rich command-line interface built with Typer for direct terminal operations. Execute farms, test proxies, list accounts, and perform administrative tasks without starting the API server.

**Structured Logging**  
Production-ready logging system using Rich library for colorful, contextual console output and Loguru for advanced log management. Track execution flow, debug issues, and monitor system health in real-time.

### Frontend Dashboard

**Reactive Control Panel**  
Modern single-page application built with Next.js 15 App Router and React 19. Real-time data visualization with instant updates as operations progress.

**Advanced Account Management**  
Comprehensive account table with search, filtering by data source, multi-select operations, and detailed status indicators. View points, activity history, and per-account metrics at a glance.

**Performance Metrics**  
Key performance indicators dashboard displaying total accounts, accumulated points, active farms, success rates, and historical trends. Make data-driven decisions about account operations.

**Operational Controls**  
Intuitive interface for adding accounts, launching batch farm operations, executing individual account runs, and managing proxy configurations. All operations provide immediate feedback and progress tracking.

**Modern UI/UX**  
Built with Tailwind CSS and shadcn/ui component library for a polished, professional appearance. Full theme support (light/dark modes), responsive design for desktop and mobile, and accessibility compliant.

**Efficient State Management**  
TanStack Query (React Query) for server state management with intelligent caching, automatic background revalidation, and optimistic updates. Zustand for client-side state coordination across components.

---

## Architecture

### System Design

Raxy Farm follows a monorepo structure with clear separation between backend and frontend concerns.

#### Backend (`raxy_project/`)

A modular monolith in Python with layered architecture:

**Application Layer (`app/`)**  
FastAPI application serving as the HTTP gateway. Controllers handle request/response, validate inputs, and delegate to core services. Provides OpenAPI documentation and CORS configuration.

**Core Library (`raxy/`)**  
The heart of the system containing all business logic:

- **`domain/`**: Core entities like `Conta` (Account) with business rules and validation logic
- **`interfaces/`**: Abstract base classes defining contracts for services, repositories, and external APIs
- **`services/`**: Business logic implementation - authentication, execution orchestration, proxy management, and scoring
- **`repositories/`**: Data access layer with implementations for file storage and database persistence
- **`api/`**: External API clients for Bing Rewards, Microsoft authentication, and Supabase
- **`core/`**: Cross-cutting concerns like configuration management and utility functions
- **`container.py`**: Dependency injection container wiring interfaces to concrete implementations
- **`proxy/`**: Proxy pool management, health checking, and rotation strategies

**CLI (`cli.py`)**  
Typer-based command-line interface for direct system interaction outside the API server.

#### Frontend (`raxy-dashboard/`)

Next.js application with modern React patterns:

- **`src/app/`**: App Router pages and route handlers
- **`src/components/`**: Reusable UI components including full shadcn/ui integration
- **`src/features/`**: Feature-specific modules with co-located components, hooks, and logic
- **`src/lib/`**: Utilities, API clients, and helper functions
- **`src/hooks/`**: Custom React hooks for shared functionality
- **`src/providers/`**: React Context providers for theming and global state
- **`src/stores/`**: Zustand stores for client-side state management

---

## Technology Stack

### Backend
- **Python 3.11+** - Modern Python with type hints and async support
- **FastAPI** - High-performance async web framework with automatic OpenAPI documentation
- **Typer** - CLI framework with automatic help generation and type validation
- **Botasaurus** - Browser automation engine for reward farming
- **Supabase Client** - Python client for Supabase database operations
- **Rich** - Terminal output formatting and progress tracking
- **Loguru** - Advanced logging with rotation, filtering, and formatting
- **Pydantic** - Data validation using Python type annotations
- **Xray/V2Ray** - Proxy protocol support via external process management

### Frontend
- **TypeScript** - Static typing for JavaScript
- **Next.js 15** - React framework with App Router and server components
- **React 19** - Modern React with concurrent features
- **Tailwind CSS** - Utility-first CSS framework
- **shadcn/ui** - High-quality accessible component library
- **TanStack Query** - Powerful asynchronous state management
- **Zustand** - Lightweight state management
- **Zod** - TypeScript-first schema validation
- **React Hook Form** - Performant form handling
- **Lucide React** - Clean, consistent icon set

---

## Installation and Setup

### Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- pnpm (recommended) or npm/yarn
- Xray or V2Ray executable in system PATH (for proxy functionality)

### Backend Configuration

1. **Navigate to backend directory:**
   ```bash
   cd raxy_project
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r ../requirements.txt
   ```

4. **Environment configuration:**
   
   Create `.env` in `raxy_project/` root:
   ```env
   # Supabase Configuration (if using database source)
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_KEY=your-supabase-anon-key
   
   # Optional: Proxy configuration
   PROXY_TEST_URL=https://www.bing.com
   ```

5. **Account configuration (file-based):**
   
   Create `users.txt` in `raxy_project/` root with accounts (one per line):
   ```
   email@example.com:password123
   another@example.com:password456
   ```

### Frontend Configuration

1. **Navigate to frontend directory:**
   ```bash
   cd raxy-dashboard
   ```

2. **Install dependencies:**
   ```bash
   pnpm install
   ```

3. **Environment configuration:**
   
   Create `.env.local` in `raxy-dashboard/` root:
   ```env
   NEXT_PUBLIC_RAXY_API_URL=http://127.0.0.1:8000
   ```

---

## Running the Application

### Backend Server

Start the FastAPI server for dashboard integration:

```bash
cd raxy_project
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API documentation available at `http://127.0.0.1:8000/docs`

### Frontend Dashboard

With the backend running, start the development server:

```bash
cd raxy-dashboard
pnpm dev
```

Access the dashboard at `http://localhost:3000`

### CLI Operations

Execute operations directly without the API server:

**Run farm with file accounts:**
```bash
cd raxy_project
python cli.py run
```

**Run farm with database accounts:**
```bash
python cli.py run --source database
```

**Test proxy pool:**
```bash
python cli.py proxy test --threads 20 --country US
```

**List file accounts:**
```bash
python cli.py accounts list-file
```

**List database accounts:**
```bash
python cli.py accounts list-db
```

---

## Project Structure

```
Raxy Farm/
├── raxy_project/              # Backend Python application
│   ├── app/                   # FastAPI application layer
│   │   ├── controllers/       # HTTP request handlers
│   │   ├── main.py           # Application entry point
│   │   └── dependencies.py   # DI container setup
│   ├── raxy/                 # Core business logic library
│   │   ├── api/              # External API clients
│   │   ├── core/             # Configuration and utilities
│   │   ├── domain/           # Domain entities
│   │   ├── interfaces/       # Abstract contracts
│   │   ├── repositories/     # Data access layer
│   │   ├── services/         # Business logic
│   │   ├── proxy/            # Proxy management
│   │   └── container.py      # DI container
│   └── cli.py                # CLI interface
├── raxy-dashboard/           # Frontend Next.js application
│   ├── src/
│   │   ├── app/              # Next.js pages
│   │   ├── components/       # UI components
│   │   ├── features/         # Feature modules
│   │   ├── hooks/            # Custom hooks
│   │   ├── lib/              # Utilities and API clients
│   │   ├── providers/        # Context providers
│   │   └── stores/           # State management
│   └── public/               # Static assets
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

---

## API Documentation

When the backend is running, comprehensive API documentation is available at:

- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

### Key Endpoints

- `GET /api/v1/accounts` - List all accounts with filtering
- `POST /api/v1/accounts` - Add new account
- `POST /api/v1/farm/run` - Execute farm for all accounts
- `POST /api/v1/farm/run/{account_id}` - Execute farm for specific account
- `GET /api/v1/metrics` - Retrieve performance metrics
- `GET /api/v1/proxies` - List available proxies
- `POST /api/v1/proxies/test` - Test proxy health

---

## Development

### Backend Development

The backend follows clean architecture principles:

1. Define entities in `raxy/domain/`
2. Create interfaces in `raxy/interfaces/`
3. Implement services in `raxy/services/`
4. Wire dependencies in `raxy/container.py`
5. Expose via controllers in `app/controllers/`

### Frontend Development

The frontend uses feature-based organization:

1. Create feature directory in `src/features/`
2. Implement components, hooks, and types
3. Add API client methods in `src/lib/api/`
4. Create pages in `src/app/` using feature components

### Testing

**Backend:**
```bash
cd raxy_project
python -m pytest raxy/tests/
```

**Frontend:**
```bash
cd raxy-dashboard
pnpm test
```

---

## Security Considerations

- Never commit `.env` or `.env.local` files
- Store sensitive credentials in environment variables
- Use service accounts with minimal required permissions
- Regularly rotate API keys and database credentials
- Review proxy sources for security and reliability
- Implement rate limiting in production deployments

---

## License

This project is provided as-is for educational and personal use. Please review Microsoft Rewards terms of service and ensure compliance with all applicable regulations.

---

## Acknowledgments

Built with modern development practices and enterprise-grade tools to provide a reliable, scalable, and maintainable solution for Microsoft Rewards automation.