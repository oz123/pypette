import json
import sys

import peewee
import pypette
from pypette import PyPette, HTTPResponse
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

    return HTTPResponse(f"{{'OK': {len(payload)} records created}}'",
                        status_code=201,
                        content_type=('Content-Type', 'application/json')
)


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

    def __init__(self, app, prefix="v1", title="", description="", version="", **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix
        self.registered_models = {}
        self.swagger_meta = {"openapi": "3.1.0", "info": {"title": title, "description": description, "version": version}}
        self._configure(app)

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

    def gen_swagger(self, request):
        return {
    "openapi": "3.1.0",
    "info": {
        "title": "People API",
        "description": "API for managing people records",
        "version": "1.0.0"
    },
    "paths": {
        "/people": {
            "get": {
                "summary": "Retrieve all people",
                "description": "Returns a list of all people in the database.",
                "responses": {
                    "200": {
                        "description": "A list of people",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {
                                                "type": "string"
                                            },
                                            "birthday": {
                                                "type": "string",
                                                "format": "date"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "summary": "Add a new person",
                "description": "Adds a new person to the database.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string"
                                    },
                                    "birthday": {
                                        "type": "string",
                                        "format": "date"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Person created successfully"
                    },
                    "400": {
                        "description": "Invalid input"
                    }
                }
            }
        }
    }
}
    def gen_docs(self, request):
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Swagger UI</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
            <script>
                SwaggerUIBundle({{
                    url: "/{self.prefix}/swagger.json",
                    dom_id: "#swagger-ui",
                }});
            </script>
        </body>
        </html>
        """

    def _configure(self, app):
        app.add_route(f"/{self.prefix}/docs", self.gen_docs)
        app.add_route(f"/{self.prefix}/swagger.json", self.gen_swagger)

admin = AdminManager(template_path='admin')
