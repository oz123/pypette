import pytest

from pypette import Router, MethodMisMatchError


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


def test_route_with_different_methods():
    router = Router()

    def get_handler(request=None):
        return "GET response"

    def post_handler(request=None):
        return "POST response"

    # Add the same path with different methods
    router.add_route("/test", get_handler, method="GET")
    router.add_route("/test", post_handler, method="POST")

    # Match GET
    callback, path_params, query_params = router.match("/test", method="GET")
    assert callback() == "GET response"

    # Match POST
    callback, path_params, query_params = router.match("/test", method="POST")
    assert callback() == "POST response"

    # Method mismatch should raise error
    with pytest.raises(MethodMisMatchError):
        router.match("/test", method="DELETE")


def test_router_merge():
    router1 = Router()
    router2 = Router()

    def handler1(request=None):
        return "from router1"

    def handler2(request=None):
        return "from router2"

    def handler2_alt(request=None):
        return "alt from router2"

    router1.add_route("/common", handler1, method="GET")
    router1.add_route("/only1", handler1, method="GET")

    router2.add_route("/common", handler2, method="GET")  # Will override
    router2.add_route("/only2", handler2_alt, method="GET")

    router1.merge(router2)

    # '/common' should now return router2's version
    callback, _, _ = router1.match("/common")
    assert callback() == "from router2"

    # '/only1' should still exist
    callback, _, _ = router1.match("/only1")
    assert callback() == "from router1"

    # '/only2' should be added from router2
    callback, _, _ = router1.match("/only2")
    assert callback() == "alt from router2"

