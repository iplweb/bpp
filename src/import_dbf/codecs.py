import codecs


def custom_encode(text: str) -> bytes:
    return text.replace("\x81", "").encode("cp1250")


def custom_decode(binary: bytes, mode: str) -> str:
    try:
        res = codecs.decode(binary, "cp1250")
        return res, len(res)
    except:
        new_bytes = "".join([chr(x) for x in binary if x != 129])
        res = codecs.decode(bytes(new_bytes, "ascii"), "cp1250")
        return res, len(res)

    raise Exception("EDOOFUS")


def custom_search_function(encoding_name):
    return codecs.CodecInfo(custom_encode, custom_decode, name='my_cp1250')


codecs.register(custom_search_function)
