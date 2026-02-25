# Contributing to Linux Desktop MCP

First off, thank you for considering contributing to Linux Desktop MCP!

## Built with Claude Code

This entire project was built using [Claude Code](https://claude.ai/claude-code), Anthropic's AI-powered coding assistant. We believe in the power of AI-assisted development and welcome contributions from both humans and AI-assisted developers alike.

## Ways to Contribute

We're very open to contributions of all kinds:

- **Bug Reports**: Found a bug? Open an issue with details about your environment and steps to reproduce.
- **Feature Requests**: Have an idea? We'd love to hear it! Open an issue to discuss.
- **Pull Requests**: Code contributions are welcome! See below for guidelines.
- **Documentation**: Help improve our docs, add examples, or fix typos.
- **Forks**: Feel free to fork this project and build your own version! We'd love to see what you create.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/BeckhamLabsLLC/linux-desktop-mcp.git
   cd linux-desktop-mcp
   ```

2. **Install system dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt install python3-pyatspi gir1.2-atspi-2.0 at-spi2-core

   # For input simulation (pick one or more)
   sudo apt install ydotool  # Wayland + X11
   sudo apt install xdotool  # X11 only
   ```

3. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

5. **Run tests**
   ```bash
   pytest tests/
   ```

## Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting. Before submitting:

```bash
pip install ruff
ruff check .
ruff format .
```

### Guidelines

- Follow PEP 8 style guidelines
- Add type hints to function signatures
- Write docstrings for public functions and classes
- Keep functions focused and reasonably sized
- Add tests for new functionality

## Pull Request Process

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** with clear, descriptive commits
3. **Add tests** if you're adding new functionality
4. **Run the test suite** to ensure nothing is broken
5. **Update documentation** if needed
6. **Open a Pull Request** with a clear description of changes

### PR Title Format

Use clear, descriptive titles:
- `feat: Add support for Wayland layer shell`
- `fix: Handle closed windows gracefully`
- `docs: Add troubleshooting section`
- `test: Add tests for reference manager`

## Reporting Bugs

When reporting bugs, please include:

1. **Your environment**: Linux distro, display server (X11/Wayland), compositor
2. **Steps to reproduce**: Clear steps to trigger the bug
3. **Expected behavior**: What should happen
4. **Actual behavior**: What actually happens
5. **Logs**: Any relevant error messages or logs

## Feature Requests

For feature requests, please describe:

1. **The problem** you're trying to solve
2. **Your proposed solution** (if you have one)
3. **Alternatives** you've considered

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open an issue for any questions about contributing. We're happy to help!
