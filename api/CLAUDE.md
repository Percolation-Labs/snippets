# CLAUDE.md - Helper Guide for API Codebase

## Build Commands
- Install dependencies: `uv pip install -r requirements.txt`
- Run server: `uvicorn app.main:app --reload`
- Run test client: `python -m app.test_client`
- Run tests: `pytest`
- Run single test: `pytest tests/path_to_test.py::test_function_name -v`
- Lint code: `ruff check .`
- Format code: `black .`
- Type check: `mypy .`

## Code Style Guidelines
- **Imports**: Group standard library imports first, then third-party, then local
- **Formatting**: Use Black for formatting, line length 88 chars
- **Types**: Use type hints everywhere, leverage Pydantic for models and validation
- **Structure**: 
  - Models in `/app/models` (Pydantic objects)
  - Controllers in `/app/controllers` (business logic)
  - Routes in `/app/routers` (API endpoints)
- **Naming**: 
  - snake_case for variables, functions, modules
  - PascalCase for classes and Pydantic models
  - ALL_CAPS for constants
- **Error Handling**: Use FastAPI's HTTPException, document status codes in docstrings
- **Authentication**: Use dependency injection for auth requirements
- **Testing**: Test all endpoints, auth flows and payment workflows

## External Resources
- **FastHTML**: https://github.com/AnswerDotAI/fasthtml - A library for creating HTML interfaces for FastAPI applications
- **Test Client**: See `app/TEST_CLIENT_README.md` for documentation on using the test client to test authentication and payment flows