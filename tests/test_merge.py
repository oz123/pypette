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

