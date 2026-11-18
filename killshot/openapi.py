"""Write the API's OpenAPI schema to a file, for generating the frontend's types.

    python -m killshot.openapi web/openapi.json     (run by `npm run gen:api` in web/)
"""
import json
import sys

from .api import app


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "web/openapi.json"
    with open(path, "w") as f:
        json.dump(app.openapi(), f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
