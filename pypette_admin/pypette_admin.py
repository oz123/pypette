import json
import sys

import peewee
import peewee as pw
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
        self.title = title
        self.description = description
        self.version =  version
        self.swagger_meta = {"title": title, "description": description, "version": version}
        self._configure(app)

    def register_model(self, model, allowed_methods=None):
        """add model to API viesw"""
        if not allowed_methods:
            allowed_methods=ALLOWED_METHODS

        self.registered_models[model.__name__.lower()] = model

        for method in allowed_methods:
            print(model.__name__.lower(), f"generic_{method.lower()}", method)
            self.add_route(model.__name__.lower(),
                           getattr(sys.modules[__name__], f"rest_{method.lower()}"),
                           method=method)

    def _model_get(self, model):
        return {
            "summary": f"Retrieve all {model.__name__}",
            "description": f"Returns a list of all {model.__name__} in the database.",
            "responses": {
                    "200": {
                        "description": "A list of people",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": self.generate_openapi_schema(model)
                                }
                            }
                        }
                    }
                }
            }

    def _model_post(self, model):
        return {
                "summary": f"Add a new {model.__name__} item",
                "description": f"Adds a new {model.__name__} to the database.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": self.generate_openapi_schema(model)
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Object created successfully"
                    },
                    "400": {
                        "description": "Invalid input"
                    }
                }
            }

    def _get_models_paths(self):
        mps = {}
        for name, model in self.registered_models.items():
           mps[f"/{name}"] = {
               "get": self._model_get(model),
               "post": self._model_post(model),
           }
        return mps

    def map_field_to_openapi(self, field):
        if isinstance(field, pw.CharField):
            return {"type": "string"}
        elif isinstance(field, pw.DateField):
            return {"type": "string", "format": "date"}
        ...
        # add more mappings as needed
        return {"type": "string"}

    def generate_openapi_schema(self, model):
        """generate OpenAPI schema from a Peewee model"""
        properties = {}
        for field in model._meta.fields.values():
            properties[field.name] = self.map_field_to_openapi(field)
        return {
            "type": "object",
            "properties": properties
        }

    def gen_swagger(self, request):
        return {
            "openapi": "3.1.0",
            "info": self.swagger_meta,
            "paths": self._get_models_paths()
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
