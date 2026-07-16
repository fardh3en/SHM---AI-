"""
CLI Script to run the FastAPI development server.
"""
import sys
from pathlib import Path

import uvicorn

# Add project root to sys.path so we can import backend packages
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    """Run development server using uvicorn programmatically."""
    from backend.app.config import get_settings

    settings = get_settings()

    print(f"Starting {settings.APP_NAME} Dev Server...")
    print(f"Environment: {settings.APP_ENV}")
    print(f"Debug Mode:  {settings.DEBUG}")
    print(f"Swagger Docs: http://localhost:8000{settings.API_V1_PREFIX}/docs")

    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT / "backend")],
    )


if __name__ == "__main__":
    main()
