VERSION = "202310.1120"

if __name__ == "__main__":
    import sys

    OUTPUT = VERSION

    if "--json" in sys.argv:
        import json

        OUTPUT = json.dumps({"VERSION": VERSION})

    sys.stdout.write(OUTPUT)
