
from pypette import Router

def greet(name="world"):
    return f"Hello {name}"

def users(gid, uid):
    directory = {"100": {"1000": "moe"}}
    return directory[gid][uid]
    
def test_add_route():
    router = Router()
    router.add_route("/hello", greet)
    router.add_route("/hello/:name", greet)

    callback, path_params, query_params = router.match("/hello")
    assert callback == greet
    assert path_params == []
    assert query_params == {}
    rv = callback()

    callback, path_params, query_params = router.match("/hello/world")
    assert callback == greet
    assert path_params == ["world"]
    assert query_params == {}
    rv2 = callback()

    assert rv == rv2

def test_add_route_complex():
    router = Router()
    router.add_route("/users/:gid/:uid", users)
    callback, path_params, _ = router.match("/users/100/1000")
    assert path_params == ["100", "1000"]
    assert callback(*path_params) == "moe"


def test_route_match_with_query():
    router = Router()
    router.add_route("/users/:gid/:uid", users)
    _, _, query_params = router.match("/users/100/1000?set_lock=true")
    assert query_params == {'set_lock': 'true'}


