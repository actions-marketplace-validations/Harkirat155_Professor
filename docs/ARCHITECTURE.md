# Professor Architecture

## Overview

Professor is built with a modular, extensible architecture designed to integrate with multiple SCM platforms and support various code analysis techniques.

## Core Components

### 1. Analysis Engine (`professor.core`)

The heart of Professor, providing:

- **Models**: Data structures for findings, reviews, locations
- **Analyzer Interface**: Base classes for all analyzers
- **Composite Pattern**: Combine multiple analyzers

```
┌─────────────────────────────────┐
│      Analysis Engine            │
│  ┌──────────┐  ┌──────────┐    │
│  │  Models  │  │ Analyzer │    │
│  └──────────┘  └──────────┘    │
└─────────────────────────────────┘
```

### 2. LLM Integration (`professor.llm`)

Handles communication with AI models:

- **Provider Abstraction**: Unified interface for OpenAI, Anthropic, local models
- **Token Management**: Count tokens, estimate costs
- **Error Handling**: Retry logic, rate limiting
- **Cost Tracking**: Monitor API usage and expenses

```
┌─────────────────────────────────┐
│      LLM Layer                  │
│  ┌──────────┐  ┌──────────┐    │
│  │  OpenAI  │  │Anthropic │    │
│  └──────────┘  └──────────┘    │
└─────────────────────────────────┘
```

### 3. SCM Adapters (`professor.scm`)

Platform-specific integrations:

- **GitHub**: REST API, GraphQL, webhooks
- **GitLab**: (Planned)
- **Bitbucket**: (Planned)
- **Azure DevOps**: (Planned)

Each adapter implements a common interface:
- Fetch PR/MR data
- Get diff and file changes
- Post review comments
- Update status checks

### 4. Analyzers (`professor.analyzers`)

Pluggable analysis modules:

- **LLM Analyzer**: AI-powered code review
- **Static Analyzer**: Linters, type checkers
- **Security Scanner**: Vulnerability detection
- **Performance Analyzer**: Complexity, anti-patterns
- **Documentation Checker**: Doc coverage

### 5. Configuration (`professor.config`)

Centralized settings management:

- Environment variables
- YAML configuration files
- Pydantic models for validation
- Per-project overrides

### 6. CLI (`professor.cli`)

Command-line interface:

- Review local changes
- Analyze specific PRs
- Generate reports
- View statistics

## Data Flow

### Pull Request Review Flow

```
1. GitHub PR Event
   ↓
2. Webhook/Action Trigger
   ↓
3. Fetch PR Data (diff, files, context)
   ↓
4. Route to Analyzers
   ↓
5. LLM Analysis ← → OpenAI/Anthropic API
   Static Analysis ← → Linters
   Security Scan ← → Vulnerability DB
   ↓
6. Aggregate Findings
   ↓
7. Generate Review
   ↓
8. Post Comments to PR
   ↓
9. Update Status Check
```

### Local Review Flow

```
1. CLI Command
   ↓
2. Git Integration (get diff)
   ↓
3. Parse Changes
   ↓
4. Route to Analyzers
   ↓
5. Analysis (same as above)
   ↓
6. Format Output (JSON/Markdown/Text)
   ↓
7. Display Results
```

## Extension Points

### Adding a New Analyzer

```python
from professor.core import Analyzer, Finding

class MyAnalyzer(Analyzer):
    async def analyze(self, context):
        # Your analysis logic
        return [findings...]
    
    def supports(self, context):
        # Check if you can analyze this context
        return context.get("language") == "python"
```

### Adding a New SCM Platform

```python
from professor.scm.base import BaseSCMAdapter

class GitLabAdapter(BaseSCMAdapter):
    async def get_pull_request(self, pr_id):
        # Fetch MR data
        pass
    
    async def post_review(self, pr_id, review):
        # Post review comments
        pass
```

### Adding a New LLM Provider

```python
from professor.llm import BaseLLMClient

class LocalLLMClient(BaseLLMClient):
    async def complete(self, messages):
        # Call local model
        pass
```

## Design Principles

1. **Modularity**: Each component is independent and replaceable
2. **Extensibility**: Easy to add new platforms, analyzers, LLMs
3. **Type Safety**: Strong typing with Pydantic and mypy
4. **Async-First**: Non-blocking I/O for performance
5. **Testability**: Dependency injection, mockable interfaces
6. **Configuration**: Flexible, validated configuration system
7. **Observability**: Structured logging, metrics, tracing

## Technology Choices

- **Python 3.11+**: Modern Python features, performance improvements
- **Pydantic**: Data validation and settings management
- **FastAPI**: High-performance web framework
- **Structlog**: Structured logging
- **Click**: CLI framework
- **Rich**: Beautiful terminal output
- **pytest**: Testing framework
- **Ruff**: Fast linting
- **Black**: Code formatting
- **mypy**: Static type checking

## Future Architecture Enhancements

- **Plugin System**: Dynamic plugin discovery and loading
- **Distributed Analysis**: Parallel analysis across workers
- **Caching Layer**: Redis-based caching for repeated analyses
- **ML Pipeline**: Fine-tuned models for specific domains
- **Real-time Streaming**: WebSocket updates for long-running reviews
- **Multi-tenant**: Support for multiple organizations
