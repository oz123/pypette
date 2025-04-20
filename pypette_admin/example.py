from wsgiref.simple_server import make_server

from pypette import PyPette


myapp = PyPette()


@myapp.route("/hello")
def hello(request):
    return "hello"


from pypette_admin import admin


class People:
    ...

admin.register_model(People)

myapp.mount("/admin", admin)

httpd = make_server('', 8000, myapp)
print("Serving on port 8000...")

myapp.resolver.print_trie()

# Serve until process is killed
httpd.serve_forever()
