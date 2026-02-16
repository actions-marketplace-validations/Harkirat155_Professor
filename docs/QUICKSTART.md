# 🎓 Professor - Quick Start Guide

## Installation

```bash
cd Professor

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install pydantic pydantic-settings click rich structlog pyyaml python-dotenv PyGithub anthropic openai langchain pytest pytest-asyncio

# Set PYTHONPATH
export PYTHONPATH="${PWD}/src"  # Windows: $env:PYTHONPATH = "${PWD}\src"
```

## Configuration

Create a `.env` file in the project root:

```bash
# Required: GitHub access
GITHUB_TOKEN=ghp_your_github_token_here

# Required: At least one LLM provider
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here
# OR
OPENAI_API_KEY=sk-your_openai_key_here

# Optional: Customize settings
PROFESSOR_ENV=development
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-3-5-sonnet-20240620
LOG_LEVEL=INFO
MAX_REVIEW_FILES=50
```

## Usage

### Review a GitHub Pull Request

```bash
# Using PR URL
professor review --pr-url https://github.com/octocat/Hello-World/pull/1

# Using owner/repo/number
professor review --owner octocat --repo Hello-World --pr-number 1

# Filter by minimum severity
professor review --pr-url https://github.com/owner/repo/pull/123 --min-severity high

# Post comments to GitHub (coming soon)
professor review --pr-url https://github.com/owner/repo/pull/123 --post-comments
```

### Initialize Configuration

```bash
# Create professor.yaml in current directory
professor init

# Show current configuration
professor config-show
```

### View Statistics (coming soon)

```bash
# Show review statistics
professor stats

# Last 7 days
professor stats --days 7
```

## Example Output

```
🎓 Professor Code Review
Analyzing code with superhuman precision...

Initializing Professor for octocat/Hello-World#1...
✓ Review Complete!

PR: Add new feature
Author: octocat
Files Analyzed: 5
Cost: $0.0234

📊 Review Summary
┏━━━━━━━━━━┳━━━━━━━┓
┃ Severity ┃ Count ┃
┡━━━━━━━━━━╇━━━━━━━┩
│ Critical │     0 │
│ High     │     2 │
│ Medium   │     3 │
│ Low      │     1 │
│ Info     │     4 │
│          │       │
│ Total    │    10 │
└──────────┴───────┘

🔍 Findings (>= medium):

● HIGH: Potential null pointer dereference
  📍 src/main.py:42
  💬 Variable 'data' could be None when accessed without null check
  💡 Suggestion: Add null check: if data is not None:

● HIGH: SQL injection vulnerability
  📍 src/database.py:15
  💬 User input directly interpolated into SQL query
  💡 Suggestion: Use parameterized queries

● MEDIUM: Missing error handling
  📍 src/api.py:88
  💬 Network request without try-except block
  💡 Suggestion: Wrap in try-except to handle connection errors

✗ PR BLOCKED - 2 blocking issue(s)
```

## Configuration File

Create `professor.yaml` in your project:

```yaml
professor:
  version: 1
  
  standards:
    severity_threshold: medium
    auto_approve_threshold: low
    max_critical_issues: 0
    max_high_issues: 3

  analyzers:
    - llm:
        provider: anthropic
        model: claude-3-5-sonnet-20240620
        temperature: 0.1
        
  rules:
    max_file_changes: 50
    max_file_size_kb: 500
    
  ignore:
    - "**/*.generated.py"
    - "**/migrations/**"
```

## Python API

Use Professor programmatically:

```python
import asyncio
from professor.scm.github import GitHubClient
from professor.llm import AnthropicClient
from professor.reviewer import PRReviewer

async def review_pr():
    # Initialize clients
    github = GitHubClient(token="ghp_...")
    llm = AnthropicClient(api_key="sk-ant-...", model="claude-3-5-sonnet-20240620")
    
    # Create reviewer
    reviewer = PRReviewer(github_client=github, llm_client=llm)
    
    # Review PR
    result = await reviewer.review_pull_request("owner", "repo", 123)
    
    # Check results
    print(f"Total findings: {result.total_findings}")
    print(f"Approved: {result.approved}")
    print(f"Cost: ${result.cost:.4f}")
    
    # Access findings
    for finding in result.review.findings:
        if finding.severity == "critical":
            print(f"CRITICAL: {finding.title} at {finding.location}")

asyncio.run(review_pr())
```

## GitHub Actions Integration (Coming Soon)

Add to `.github/workflows/professor.yml`:

```yaml
name: Professor Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Professor Review
        uses: professor-ai/action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Troubleshooting

### "GITHUB_TOKEN not set"
- Create a GitHub personal access token with `repo` scope
- Add to `.env` file: `GITHUB_TOKEN=ghp_...`

### "ANTHROPIC_API_KEY not set"
- Get API key from https://console.anthropic.com/
- Add to `.env` file: `ANTHROPIC_API_KEY=sk-ant-...`

### "Rate limit exceeded"
- GitHub: Wait for rate limit reset or use authenticated token
- Anthropic/OpenAI: Reduce concurrent requests or upgrade plan

### "File too large"
- Adjust `MAX_FILE_SIZE_KB` in `.env`
- Or add file to ignore patterns in `professor.yaml`

## Support

- 📖 Docs: [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/professor/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/professor/discussions)

---

**Professor is ready to ensure quality in the age of AI-assisted development!** 🎓✨
