## Development Rules

### Python Development Standards

1. **Code Formatting**: Always format Python files with ruff after creation or modification
   ```bash
   ruff format <file.py>
   ```

2. **Best Practices**: Apply best practices by default for:
   - Directory structure organization
   - Function design and naming
   - Code organization and modularity
   - Error handling and logging

3. **Data Validation**: Always use Pydantic instead of dataclasses for data models

4. **Package Management**: Use `uv` instead of pip for all package installations
   ```bash
   uv pip install <package>
   ```

5. **File Size Limit**: Keep Python files under 1000 lines for better readability and maintainability

6. **FastAPI Structure**:
   - Organize endpoints into separate routers
   - Configure both Scalar and Swagger documentation
   - Follow modular architecture patterns

7. **Code Comments**: Write all comments in Italian

8. **Emoji Policy**: NEVER use emojis in source code