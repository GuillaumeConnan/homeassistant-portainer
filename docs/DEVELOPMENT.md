# Development Environment Setup

This guide explains how to develop the Portainer Home Assistant integration
with a local Python virtual environment. No editor or dev container configuration
is required.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Debugging](#debugging)
- [Contributing](#contributing)

## Prerequisites

- **Python 3.14.2 or newer**: required by Home Assistant 2026.9.0.
- **Linux**: use Linux directly, WSL, or a Linux container to run Home Assistant.
- **Git** and an editor of your choice.

## Environment Setup

```bash
git clone https://github.com/GuillaumeConnan/homeassistant-portainer.git
cd homeassistant-portainer
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
```

`requirements-test.txt` includes the runtime requirements and only the plugins
used by the tests: pytest, pytest-asyncio, and pytest-cov. HTTP requests are mocked
with the standard library's `unittest.mock`.

For code quality tools, install tox separately with
`python -m pip install "tox>=4.67.1"` and use `tox -e lint`, `tox -e security`,
or `tox -e format`. Each environment installs its own tools. Pipenv users can
alternatively use `pipenv install --dev`; the Pipfile mirrors the same
runtime and test dependencies.

CI runs Python 3.14 and tests both Home Assistant 2026.9.0 and the latest compatible
release. To check the minimum locally:

```bash
python -m pip install -r requirements-test.txt "homeassistant==2026.9.0"
python -m pytest
```

## Development Workflow

### Daily Development

1. **Start Development**
   ```bash
   # Activate the environment in each new shell
   source .venv/bin/activate
   ```

2. **Code Development**
   ```bash
   # Edit files normally
   # Use your preferred editor
   # Configure formatting and linting locally if desired
   ```

3. **Run Tests**
   ```bash
   # Run all tests
   python -m pytest

   # Run specific test file
   python -m pytest tests/unit/test_coordinator.py -v

   # Run with coverage
   python -m pytest --cov=custom_components.portainer
   ```

4. **Check Code Quality**
   ```bash
   # Format code
   tox -e format

   # Check formatting and linting
   tox -e lint
   ```

### Integration Testing

#### **Test with Home Assistant**
```bash
# Start Home Assistant in the activated Linux environment
python -m homeassistant --config config/

# Test integration loading
# Check logs for any errors
```

#### **Manual Testing**
```bash
# Test specific functionality
python3 -c "
import sys
sys.path.append('.')
from custom_components.portainer.coordinator import PortainerCoordinator
# Add your test code here
"
```

## Testing

### Test Structure

```
tests/
├── unit/                 # Unit tests
│   ├── test_api.py      # API functionality tests
│   ├── test_coordinator.py  # Coordinator logic tests
│   └── test_entity.py   # Entity creation tests
├── integration/         # Integration tests
│   └── test_portainer_integration.py
└── fixtures/           # Test data
    ├── api_responses.py    # Mock API responses
    ├── config_fixtures.py  # Configuration test data
    └── entity_fixtures.py  # Entity test data
```

### Running Tests

#### **All Tests**
```bash
python -m pytest
```

#### **Unit Tests Only**
```bash
python -m pytest tests/unit/ -v
```

#### **Integration Tests Only**
```bash
python -m pytest tests/integration/ -v
```

#### **Specific Test File**
```bash
python -m pytest tests/unit/test_coordinator.py -v
```

#### **With Coverage**
```bash
python -m pytest --cov=custom_components.portainer --cov-report=html
```

#### **Verbose Output**
```bash
python -m pytest -v -s
```

### Writing Tests

#### **Test File Template**
```python
"""Unit tests for Portainer component."""

import pytest
from unittest.mock import Mock, patch

class TestPortainerComponent:
    """Test cases for Portainer component."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        # Test fixture setup
        pass

    def test_component_functionality(self, mock_hass):
        """Test component functionality."""
        # Test implementation
        assert True
```

#### **Mock Setup**
```python
# Mock Home Assistant
mock_hass = Mock()
mock_hass.config_entries = Mock()

# Mock config entry
config_entry = Mock()
config_entry.entry_id = "test_entry_id"
config_entry.data = {"host": "localhost", "api_key": "test"}

# Mock API
mock_api = Mock()
mock_api.connected.return_value = True
```

## Debugging

### Debug Configuration

#### **Python Debugger**

1. **Set Breakpoints**: Click in the gutter next to line numbers
2. **Start Debugging**: Press `F5` or use Debug panel
3. **Debug Console**: View variables and expressions

#### **Debug Test Files**
```bash
# Debug specific test
python -m pytest tests/unit/test_coordinator.py::TestPortainerCoordinator::test_specific_function -v -s
```

### Common Debug Scenarios

#### **Integration Not Loading**
```bash
# Check manifest.json syntax
python3 -c "
import json
with open('custom_components/portainer/manifest.json') as f:
    manifest = json.load(f)
    print('Manifest valid:', bool(manifest))
"
```

#### **API Connection Issues**
```bash
# Test API connectivity manually
python3 -c "
import sys
sys.path.append('.')
from custom_components.portainer.api import PortainerAPI

# Test API connection
api = PortainerAPI(hass=None, host='localhost', api_key='test', ssl=False, verify_ssl=False)
print('API connected:', api.connected())
"
```

#### **Configuration Issues**
```bash
# Validate config flow
python3 -c "
import sys
sys.path.append('.')
from custom_components.portainer.config_flow import PortainerConfigFlow

# Test config flow
flow = PortainerConfigFlow()
print('Config flow created successfully')
"
```

## Contributing

### Development Setup

1. **Clone the Repository**
   ```bash
   # Clone the independently maintained repository
   git clone https://github.com/GuillaumeConnan/homeassistant-portainer.git
   cd homeassistant-portainer
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/amazing-new-feature
   ```

3. **Make Changes**
   ```bash
   # Edit files, run tests, format code
   # Ensure all tests pass
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "Add amazing new feature"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/amazing-new-feature
   # Create Pull Request on GitHub
   ```

### Code Quality Standards

#### **Formatting**
- **Black**: Code formatting (`tox -e format`)
- **Line Length**: 88 characters (Black default)
- **Quotes**: Double quotes preferred

#### **Linting**
- **Pylint**: Error checking (`tox -e lint`)
- **Type Hints**: Use for all function parameters and returns
- **Docstrings**: Google style for modules and classes

#### **Testing**
- **Test Coverage**: Aim for >90% coverage
- **Test Isolation**: Each test should be independent
- **Mock External Dependencies**: Use mocks for HA components and APIs

### Pull Request Process

1. **Create PR**: Use GitHub interface
2. **CI/CD**: Automated tests run automatically
3. **Review**: Maintainers review changes
4. **Merge**: Approved PRs are merged

### Best Practices

#### **Code Organization**
```
custom_components/portainer/
├── __init__.py          # Integration setup
├── api.py              # Portainer API client
├── config_flow.py      # Configuration UI
├── coordinator.py      # Data coordination
├── const.py           # Constants and types
├── sensor.py          # Sensor entities
├── button.py          # Button entities
├── services.yaml      # Service definitions
└── manifest.json      # Integration metadata
```

#### **Error Handling**
```python
# Always handle exceptions gracefully
try:
    result = risky_operation()
except SpecificException as e:
    _LOGGER.error("Operation failed: %s", e)
    return None
```

#### **Type Hints**
```python
# Use proper type hints
from typing import Optional, Dict, Any

def process_data(data: Dict[str, Any]) -> Optional[str]:
    """Process data with proper type hints."""
    if not data:
        return None
    return data.get("key")
```

## Troubleshooting Dev Environment

#### **Python Path Issues**
```bash
# Check the active interpreter (Python 3.14.2 minimum)
python --version
python -c "import sys; print(sys.executable)"

# Verify the installed Home Assistant version
python -m pip show homeassistant
```

### Common Development Issues

#### **Import Errors**
```bash
# Ensure the virtual environment is active
# Check if file exists and has correct permissions
ls -la custom_components/portainer/

# Verify Python path includes project
python3 -c "import sys; print(sys.path)"
```

#### **Test Failures**
```bash
# Run tests with verbose output
python -m pytest -v -s

# Check for missing dependencies
pip list | grep homeassistant

# Verify test fixtures
ls -la tests/fixtures/
```

#### **Git Issues**
```bash
# Check your local Git configuration
git config --list
```

## Performance Tips

### Development Speed

1. **Use VS Code Features**
   - **IntelliSense**: Faster coding with auto-completion
   - **Live Formatting**: Black formats as you type
   - **Error Detection**: Pylint catches issues immediately

2. **Efficient Testing**
   ```bash
   # Run only changed tests
   python -m pytest tests/unit/test_coordinator.py -v

   # Use pytest-watch for auto-running tests
   pip install pytest-watch
   ptw tests/unit/test_coordinator.py
   ```

3. **Debug Efficiently**
   ```bash
   # Use Python debugger
   import pdb; pdb.set_trace()

   # Or use VS Code debugger
   # Set breakpoints and use F5
   ```

## Getting Help

### Development Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/GuillaumeConnan/homeassistant-portainer/issues)
- **Documentation**: Check this development guide and other docs in `/docs`

- **Python Development**: [Python documentation](https://docs.python.org/3/)

## Advanced Configuration

### Custom Testing Setup

#### **Test Configuration**
```bash
# Create tests/conftest.py for shared fixtures
import pytest

@pytest.fixture
def mock_hass():
    """Create shared Home Assistant mock."""
    # Shared test setup
```

#### **Test Data Management**
```bash
# Use fixtures for test data
@pytest.fixture
def sample_container_data():
    """Provide sample container data for tests."""
    return {
        "Id": "test123",
        "Name": "test-container",
        "State": "running"
    }
```

## Release Process

### Pre-Release Checklist

- [ ] All tests pass
- [ ] Code formatted with Black
- [ ] No Pylint errors
- [ ] Documentation updated
- [ ] Version bumped in manifest.json
- [ ] Changelog updated

### Release Steps

`CHANGELOG.md` is the source of truth for release notes. Every pull request with
user-visible changes adds entries under `[Unreleased]`, using `Added`, `Changed`,
`Fixed`, `Removed`, `Security`, and `Migration notes` as applicable. Describe the
behavior and migration impact, not just the commit title; link related PRs when useful.

1. **Prepare the changelog and version**

   Move the accumulated entries from `[Unreleased]` into a section named exactly
   `## [2.0.0] - YYYY-MM-DD`, replacing the date with the real release date. Keep an
   empty `[Unreleased]` section above it for future changes. Update
   `custom_components/portainer/manifest.json` to `"version": "2.0.0"`.

2. **Run Full Test Suite**
   ```bash
   python -m pytest
   ```
   The release-note tests can also run without Home Assistant:
   ```bash
   python -m unittest discover -s tests/release -v
   ```

3. **Preview release notes and check formatting**
   ```bash
   python .github/generate_releasenotes.py --tag v2.0.0 --output release-notes-preview.md
   tox -e lint
   ```
   Review the preview, including security and migration guidance, then remove the
   preview file. Extraction requires a unique dated section with actual content.
   Both `2.0.0` and `v2.0.0` tags map to the `[2.0.0]` section.

4. **Merge the preparation PR, tag its commit on master, then publish the GitHub release**

   After merging the preparation changes and updating your checkout:
   ```bash
   git tag v2.0.0
   git push origin v2.0.0
   ```
   Create and publish a GitHub release using that tag. The release workflow checks
   out the tag, validates and extracts its changelog section, and replaces the
   GitHub release body with that section. It appends a comparison to the nearest
   ancestor version tag when one exists; the first release needs no previous tag.
   The release title is left unchanged.

   Validation runs before packaging or uploading `portainer.zip`. A missing,
   duplicate, empty or invalidly dated section fails the workflow; it never falls
   back to commit titles. Because this workflow is triggered after publication,
   failure does not unpublish the GitHub release or delete existing assets.
   Prepare and preview the notes before publishing.

   To correct published notes, update the changelog for a future release rather
   than moving an existing tag. Manual edits to the GitHub release body are not
   the source of truth and will be replaced if its workflow is rerun.

### Release Deployment Issues
If you experience issues after deploying a new release:

**GitHub Release Cache Issue:**
If you reuse a version tag that was previously used for a failed release, GitHub Actions may use cached build artifacts from the previous release instead of building fresh ones.

**Symptoms:**
- Integration works in development but fails in production
- No containers are found despite correct configuration
- API calls succeed but return empty data

**Solutions:**
1. **Use unique version tags** for each release (recommended)
2. **Clear GitHub Actions cache** in repository Settings → Actions → Caches
3. **Force fresh deployment** by updating the release workflow to clear cache when tags are reused

**Verification:**
- Check that the deployed `manifest.json` version matches your intended release
- Verify all integration files are present and up-to-date in the HACS integration directory
