
from pypette import _lscmp, _cookie_encode, _cookie_decode, _cookie_is_encoded

SECRET="someRandomSecert123#"

encoded = _cookie_encode("token", "myverysecrettoken", SECRET)

assert isinstance(encoded, bytes)
assert _cookie_is_encoded(encoded) == True

value = _cookie_decode(encoded.decode(), SECRET)

