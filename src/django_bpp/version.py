VERSION = "202506.1182"

if __name__ == "__main__":
    import sys

    OUTPUT = VERSION

    if "--json" in sys.argv:
        import json

        OUTPUT = json.dumps({"VERSION": VERSION})

    sys.stdout.write(OUTPUT)
