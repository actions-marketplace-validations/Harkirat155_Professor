# Contributing to Professor

Thank you for your interest in contributing to Professor! This document provides guidelines and instructions for contributing.

## 🎯 How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- Clear and descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Code samples if applicable
- Environment details (Python version, OS, etc.)

### Suggesting Enhancements

Enhancement suggestions are welcome! Please:

- Use a clear and descriptive title
- Provide detailed description of the proposed feature
- Explain why this enhancement would be useful
- Include code examples if applicable

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`pytest`)
6. Run linting (`ruff check . && black --check . && mypy src/professor`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## 🧪 Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/professor.git
cd professor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## 📝 Coding Standards

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for all public functions and classes
- Keep functions focused and small
- Aim for 80%+ test coverage
- Use meaningful variable and function names

## 🧪 Testing

- Write tests for all new features
- Ensure existing tests pass
- Aim for high code coverage
- Use pytest fixtures for common setup
- Mock external dependencies (API calls, etc.)

## 📖 Documentation

- Update README.md if adding user-facing features
- Add docstrings to all public APIs
- Update configuration examples if needed
- Add examples for new features

## 🔀 Git Workflow

- Keep commits atomic and focused
- Write clear commit messages
- Rebase on main before submitting PR
- Squash commits if requested

## 🎓 Code Review Process

1. Automated checks must pass (tests, linting, type checking)
2. At least one maintainer review required
3. Address all review comments
4. Maintainer will merge when approved

## 🌟 Recognition

Contributors will be acknowledged in:
- README.md contributors section
- Release notes
- GitHub contributors page

## 📞 Questions?

Feel free to ask questions by:
- Opening a GitHub issue
- Joining our Discord community
- Emailing the maintainers

Thank you for contributing to Professor! 🎓
