VERSION = "1.0.28-alpha"

if __name__ == "__main__":
    import sys

    OUTPUT = VERSION

    if "--json" in sys.argv:
        import json
        OUTPUT = json.dumps({"VERSION": VERSION})

    sys.stdout.write(OUTPUT)
