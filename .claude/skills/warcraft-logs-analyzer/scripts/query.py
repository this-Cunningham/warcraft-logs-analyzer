"""query.py - run a GraphQL query against the WCL public API and print JSON.

Usage:
    python query.py --query-file ./queries/report-summary.graphql --variables '{"code":"abc123"}'
    python query.py --query 'query { rateLimitData { limitPerHour pointsSpentThisHour } }'

Output is pretty-printed JSON on stdout, suitable for piping or capturing.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
import lib


def main(argv=None):
    p = argparse.ArgumentParser(description="Run a WCL GraphQL query and print JSON.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--query", help="inline GraphQL query string")
    g.add_argument("--query-file", help="path to a .graphql file")
    p.add_argument("--variables", help='JSON object string, e.g. \'{"code":"abc","fightIDs":[1,2]}\'')
    p.add_argument("--out-file", help="optional: also write JSON to this path")
    args = p.parse_args(argv)

    if args.query_file:
        with open(args.query_file, "r", encoding="utf-8-sig") as fh:
            query = fh.read()
    else:
        query = args.query

    variables = json.loads(args.variables) if args.variables else None

    data = lib.invoke_query(query, variables)
    out = json.dumps(data, indent=2, ensure_ascii=False)

    if args.out_file:
        with open(args.out_file, "w", encoding="utf-8") as fh:
            fh.write(out)
    sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
