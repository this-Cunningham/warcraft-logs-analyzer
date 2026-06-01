"""introspect.py - one-time GraphQL schema dump for the WCL public API.

Saves the full introspection result to schema.json at the repo root so the skill
(and you) can browse types/fields without guessing.

    python introspect.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
import lib

INTROSPECTION = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args { name description type { ...TypeRef } }
        type { ...TypeRef }
      }
      inputFields { name description type { ...TypeRef } }
      enumValues(includeDeprecated: true) { name description }
    }
  }
}
fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
}
"""


def main():
    data = lib.invoke_query(INTROSPECTION)
    out = os.path.join(lib.find_repo_root(), "schema.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print("Schema written to " + out)


if __name__ == "__main__":
    main()
