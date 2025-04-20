import sys

from pypette import PyPette

ALLOWED_METHODS=["GET", "POST", "DELETE"]


def generic_get(request):
    return admin.templates.load('table.html').render({"method": request.method,
                                                      "rows": [],
                                                      "admin_prefix": admin.prefix,
                                                      "title": request.path.split("/")[-1]})


def generic_delete(request):
    return admin.templates.load('table.html').render({"method":request.method})


def generic_post(request):
    return admin.templates.load('table.html').render({"method":request.method,
                                                      "title": "asdasd"
                                                     })


REGISTERED_MODELS=[]


def list_registered(request):
    return admin.templates.load('admin.html').render({"models":
                                                      [m.lower() for m in REGISTERED_MODELS],
                                                      "title": "Modles Admin",
                                                      "method": request.method,
                                                      "admin_prefix": admin.prefix})


class AdminManager(PyPette):
    """An app to add admin views for PeeWee models
    """

    def __init__(self, prefix="admin", **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix
        self.add_route("/", list_registered, method="GET")

    def register_model(self, model, allowed_methods=None):
        """add an admin view"""
        if not allowed_methods:
            allowed_methods=ALLOWED_METHODS

        REGISTERED_MODELS.append(model.__name__)

        for method in allowed_methods:
            print(model.__name__.lower(), f"generic_{method.lower()}" ,method)
            self.add_route(model.__name__.lower(),
                           getattr(sys.modules[__name__], f"generic_{method.lower()}"),
                                   method=method)
            print(self.resolver.print_trie())


admin = AdminManager(template_path='admin')
