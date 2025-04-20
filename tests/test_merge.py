from pypette import Router



def func1():
    print(1)

def func2():
    print(1)

def greeter(name):
    print(f"Hello {name}")


router = Router()
router2 = Router()

router.add_route("/foo", func1)
router2.add_route("/bar", func2)
router2.add_route("/greet/:name", greeter)
router.add_route("/greet/:name", greeter)

router.mount("two/", router2)

router.print_trie()


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

