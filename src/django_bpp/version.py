VERSION = "202111.1081rc6"

if __name__ == "__main__":
    import sys

    OUTPUT = VERSION

    if "--json" in sys.argv:
        import json

        OUTPUT = json.dumps({"VERSION": VERSION})

    sys.stdout.write(OUTPUT)
