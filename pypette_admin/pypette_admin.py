import json
import sys

import peewee
import pypette
from pypette import PyPette
from playhouse.shortcuts import model_to_dict

ALLOWED_METHODS=["GET", "POST", "DELETE"]


def generic_get(request: pypette.HTTPRequest):

    model_name = request.path.split("/")[-1]
    model = REGISTERED_MODELS[model_name]

    rows = list(model.select())
    return admin.templates.load('table.html').render({"method": request.method,
                                                      "rows": rows,
                                                      "admin_prefix": admin.prefix,
                                                      "title": model_name,
                                                      "to_row": model_to_tr})


def generic_delete(request):
    return admin.templates.load('table.html').render({"method":request.method})


def generic_post(request):
    return admin.templates.load('table.html').render({"method":request.method,
                                                      "title": "asdasd"
                                                     })
REGISTERED_MODELS = {}


def list_registered(request):
    return admin.templates.load('admin.html').render({"models":
                                                      [m.lower() for m in REGISTERED_MODELS],
                                                      "title": "Modles Admin",
                                                      "method": request.method,
                                                      "admin_prefix": admin.prefix})

def rest_get(request: pypette.HTTPRequest):
    model_name = request.path.strip("/").split("/")[-1]
    model = REGISTERED_MODELS[model_name]

    response = []
    for row in model.select():
        response.append(model_to_dict(row))

    return response

def rest_post(request: pypette.HTTPRequest):
    model_name = request.path.split("/")[-1]
    model = REGISTERED_MODELS[model_name]
    payload = json.loads(request.body.decode("utf-8"))
    db = model._meta.database
    with db.atomic():
        if isinstance(payload, dict):
            payload = [model(**payload)]
        else:
            payload = [model(**i) for i in payload]
        model.bulk_create(payload)

    return {"OK": f"{len(payload)} records created"}


def rest_delete(request: pypette.HTTPRequest):
    model_name = request.path.split("/")[-1]
    model = REGISTERED_MODELS[model_name]

    rows = list(model.select())

def model_to_tr(instance):
    """Convert a Peewee model instance to an HTML <tr>...</tr> row."""
    fields = instance._meta.fields
    cells = [f"<td>{getattr(instance, field)}</td>" for field in fields]
    return f"<tr>{''.join(cells)}</tr>"


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

        REGISTERED_MODELS[model.__name__.lower()] = model

        for method in allowed_methods:
            print(model.__name__.lower(), f"generic_{method.lower()}" ,method)
            self.add_route(model.__name__.lower(),
                           getattr(sys.modules[__name__], f"generic_{method.lower()}"),
                                   method=method)
            #print(self.resolver.print_trie())

def model_to_tr(instance):
    """Convert a Peewee model instance to an HTML <tr>...</tr> row."""
    fields = instance._meta.fields
    cells = [f"<td>{getattr(instance, field)}</td>" for field in fields]
    return f"<tr>{''.join(cells)}</tr>"


class RestManager(PyPette):
    """An app to add admin views for PeeWee models
    """

    def __init__(self, prefix="admin", **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix
        self.add_route("/", list_registered, method="GET")
        self.registered_models = {}

    def register_model(self, model, allowed_methods=None):
        """add model to API viesw"""
        if not allowed_methods:
            allowed_methods=ALLOWED_METHODS

        self.registered_models[model.__name__.lower()] = model

        for method in allowed_methods:
            print(model.__name__.lower(), f"generic_{method.lower()}" ,method)
            self.add_route(model.__name__.lower(),
                           getattr(sys.modules[__name__], f"rest_{method.lower()}"),
                                   method=method)

admin = AdminManager(template_path='admin')
