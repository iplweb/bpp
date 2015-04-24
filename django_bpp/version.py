VERSION = "0.9.1"

if __name__ == "__main__":
    import sys

    output = VERSION

    if "--json" in sys.argv:
        import json
        OUTPUT = json.dumps({"VERSION": VERSION})

    sys.stdout.write(OUTPUT)