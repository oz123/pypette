import sys

from pypette import PyPette

ALLOWED_METHODS=["GET", "POST", "DELETE"]


def generic_get(request):
    return admin.templates.load('table.html').render({"method":request.method})


def generic_delete(request):
    return admin.templates.load('table.html').render({"method":request.method})


def generic_post(request):
    return admin.templates.load('table.html').render({"method":request.method})


class AdminManager(PyPette):
    """And app to add admin views for PeeWee models
    """
    def register_model(self, model, allowed_methods=None):
        """add an admin view"""
        if not allowed_methods:
            allowed_methods=ALLOWED_METHODS
        import pdb; pdb.set_trace()
        for method in allowed_methods:
            print(model.__name__.lower(), f"generic_{method.lower()}" ,method)
            self.add_route(model.__name__.lower(),
                           getattr(sys.modules[__name__], f"generic_{method.lower()}"),
                                   method=method)
            print(self.resolver.print_trie())


admin = AdminManager(template_path='admin')
