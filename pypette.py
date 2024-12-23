from __future__ import annotations

import json
import re
import os

import urllib.parse

from typing import (Any, Callable, cast)


class TempliteSyntaxError(ValueError):
    """Raised when a template has a syntax error."""
    pass


class TempliteValueError(ValueError):
    """Raised when an expression won't evaluate in a template."""
    pass


class CodeBuilder:
    """Build source code conveniently."""

    def __init__(self, indent: int = 0) -> None:
        self.code: list[str | CodeBuilder] = []
        self.indent_level = indent

    def __str__(self) -> str:
        return "".join(str(c) for c in self.code)

    def add_line(self, line: str) -> None:
        """Add a line of source to the code."""
        self.code.extend([" " * self.indent_level, line, "\n"])

    def add_section(self) -> CodeBuilder:
        """Add a section, a sub-CodeBuilder."""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    INDENT_STEP = 4

    def indent(self) -> None:
        """Increase the current indent for following lines."""
        self.indent_level += self.INDENT_STEP

    def dedent(self) -> None:
        """Decrease the current indent for following lines."""
        self.indent_level -= self.INDENT_STEP

    def get_globals(self,
                    globals_dict: dict[str, Any] = None) -> dict[str, Any]:
        """Execute the code, and return a dict of globals it defines."""
        # Ensure the indentation level is back to zero
        assert self.indent_level == 0

        # Convert the code to a single string
        python_source = str(self)

        # Prepare the global namespace for execution
        global_namespace = globals_dict or {}
        exec(python_source, global_namespace)
        return global_namespace


class TemplateLoader:
    """A class to load templates from a given directory."""

    def __init__(self, base_path: str):
        """Initialize the loader with a base path for templates."""
        if not os.path.isdir(base_path):
            raise ValueError(f"The path {base_path} is not a valid directory.")
        self.base_path = base_path

    def get(self, template_name: str) -> str:
        """Retrieve the content of the template file."""
        template_path = os.path.join(self.base_path, template_name)
        if not os.path.isfile(template_path):
            raise FileNotFoundError(
                    f"Template {template_name} not found in {self.base_path}.")

        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()


class Templite:
    """A simple template renderer,
       now integrated with TemplateLoader for {% include %}."""

    def __init__(self,
                 text: str,
                 loader: TemplateLoader | None = None,
                 *contexts: dict[str, Any]) -> None:  # noqa: C901
        """
        Construct a Templite with the given `text`.

        `contexts` are dictionaries of values to use for future renderings.
        The `loader` is an optional TemplateLoader for handling {% include %}
        directives.
        """
        self.context = {}
        for context in contexts:
            self.context.update(context)

        self.loader = loader  # Optional loader for managing includes

        self.all_vars: set[str] = set()
        self.loop_vars: set[str] = set()

        # Build the function source code
        code = CodeBuilder()
        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered: list[str] = []

        def flush_output() -> None:
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line(f"append_result({buffered[0]})")
            elif len(buffered) > 1:
                code.add_line(f"extend_result([{', '.join(buffered)}])")
            del buffered[:]

        ops_stack = []

        # Split the template text into tokens
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)

        for token in tokens:
            if token.startswith("{"):
                if token.startswith("{{"):
                    # Expression to evaluate
                    expr = self._expr_code(token[2:-2].strip())
                    buffered.append(f"to_str({expr})")
                elif token.startswith("{#"):
                    # Comment: ignore it
                    continue
                elif token.startswith("{%"):
                    flush_output()
                    words = token[2:-2].strip().split()
                    if words[0] == "include":
                        if len(words) != 2:
                            self._syntax_error("Invalid syntax for include",
                                               token)
                        include_name = words[1].strip('"\'')
                        if not self.loader:
                            self._syntax_error(
                                "TemplateLoader required for include",
                                token)
                        # Add a placeholder for dynamic inclusion at
                        # render time
                        code.add_line(
                            f"append_result(Templite(loader.get({repr(include_name)}), loader).render(context))"  # noqa
                        )
                    elif words[0] == "if":
                        if len(words) != 2:
                            self._syntax_error("Invalid if statement", token)
                        ops_stack.append("if")
                        code.add_line(f"if {self._expr_code(words[1])}:")
                        code.indent()
                    elif words[0] == "else":
                        if not ops_stack or ops_stack[-1] != "if":
                            self._syntax_error("Else without matching if",
                                               token)
                        code.dedent()
                        code.add_line("else:")
                        code.indent()
                    elif words[0] == "for":
                        if len(words) != 4 or words[2] != "in":
                            self._syntax_error("Invalid for loop", token)
                        ops_stack.append("for")
                        self._variable(words[1], self.loop_vars)
                        code.add_line(f"for c_{words[1]} in {self._expr_code(words[3])}:")  # noqa
                        code.indent()
                    elif words[0].startswith("end"):
                        end_what = words[0][3:]
                        if not ops_stack or ops_stack[-1] != end_what:
                            self._syntax_error("Mismatched end tag", token)
                        ops_stack.pop()
                        code.dedent()
                    else:
                        self._syntax_error("Unknown tag", token)
            else:
                # Literal content
                if token:
                    buffered.append(repr(token))

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line(f"c_{var_name} = context[{var_name!r}]")

        code.add_line("return ''.join(result)")
        code.dedent()

        # Add Templite to the globals for render_function
        self._render_function = cast(
            Callable[[dict[str, Any], Callable[..., Any]], str],
            code.get_globals({"Templite": Templite, "loader": loader})["render_function"]  # noqa
        )

    def _expr_code(self, expr: str) -> str:
        """Generate Python code for an expression."""
        if "|" in expr:
            parts = expr.split("|")
            code = self._expr_code(parts[0])
            for func in parts[1:]:
                self._variable(func, self.all_vars)
                code = f"c_{func}({code})"
        elif "." in expr:
            parts = expr.split(".")
            code = self._expr_code(parts[0])
            for part in parts[1:]:
                code = f"do_dots({code}, {repr(part)})"
        else:
            self._variable(expr, self.all_vars)
            code = f"c_{expr}"
        return code

    def _syntax_error(self, msg: str, thing: Any) -> None:
        """Raise a syntax error."""
        raise TempliteSyntaxError(f"{msg}: {thing!r}")

    def _variable(self, name: str, vars_set: set[str]) -> None:
        """Add a variable name to a set."""
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", name):
            self._syntax_error("Invalid variable name", name)
        vars_set.add(name)

    def render(self, context: dict[str, Any]) -> str:
        """Render the template with a given context."""
        return self._render_function(context, self._do_dots)

    def _do_dots(self, value: Any, *dots: str) -> Any:
        """Resolve dotted expressions."""
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                try:
                    value = value[dot]
                except (TypeError, KeyError):
                    raise TempliteValueError(
                            f"Cannot resolve {dot} in {value}")
            if callable(value):
                value = value()
        return value


class TemplateEngine:

    def __init__(self, loader: TemplateLoader):
        self.loader = loader

    def load(self, template: str):
        return Templite(self.loader.get(template), self.loader)


class TrieNode:
    def __init__(self, path="/", method="GET"):
        self.children = {}
        self.rule = path  # The path of this route
        self.method = method  # HTTP method, e.g., GET, POST
        self.callback = None  # The handler function
        self.name = None  # Optional name of the route
        self.is_dynamic = False  # Indicate if a node represents a dynamic path

    def call(self, *args, **kwargs):
        """Invoke the callback with the provided arguments."""
        if not self.callback:
            raise ValueError("No callback defined for this route.")
        return self.callback(*args, **kwargs)

    def __repr__(self):
        return (
            f"TrieNode(path={self.rule}, method={self.method}, "
            f"callback={self.callback.__name__ if self.callback else None}, "
            f"is_dynamic={self.is_dynamic})"
        )


class MethodMisMatchError(ValueError):
    pass


class NoHandlerError(ValueError):
    pass


class NoPathFoundError(ValueError):
    pass


class Router:
    def __init__(self):
        self.root = TrieNode(path="/")

    def add_route(self, path, handler, method="GET"):
        """Add a route and associate it with a handler."""
        parts = self._split_path(path)
        current_node = self.root
        current_path = ""

        for part in parts:
            is_dynamic = part.startswith(":")
            # Use ":" as a wildcard for dynamic parts
            key = ":" if is_dynamic else part

            if key not in current_node.children:
                # Compute the path for the child node
                child_path = f"{current_path}/{part}" if \
                        current_path else f"/{part}"
                current_node.children[key] = TrieNode(path=child_path,
                                                      method=method)
                if is_dynamic:
                    current_node.children[key].is_dynamic = True

            current_node = current_node.children[key]
            current_path = current_node.rule

        current_node.callback = handler

    def get(self, full_path, method="GET"):
        """Find and call the appropriate handler for a full path with query
        parameters."""
        # Split path and query parameters
        path, _, query_string = full_path.partition("?")
        query_params = self._parse_query_string(query_string)
        # Match the route and collect path parameters
        parts = self._split_path(path)
        current_node = self.root
        path_params = []

        for part in parts:
            if part in current_node.children:
                # Match static parts
                current_node = current_node.children[part]
            elif ":" in current_node.children:
                # Match dynamic parts
                current_node = current_node.children[":"]
                path_params.append(part)
            else:
                raise NoPathFoundError(f"No route matches path: {path}")

        if current_node.method != method:
            raise MethodMisMatchError(
                f"Method not allowed for path {path}. Expected {current_node.method}."  # noqa
            )

        if not current_node.callback:
            raise NoHandlerError(f"No handler found for path: {path}")

        return current_node.callback, path_params, query_params

    def print_trie(self, node=None, depth=0):
        """Recursively print the Trie structure."""
        if node is None:
            node = self.root

        indent = "  " * depth
        handler_name = node.callback.__name__ if node.callback else None
        print(f"{indent}{node.rule} (Method: {node.method}, Handler: {handler_name})")  # noqa

        for child in node.children.values():
            self.print_trie(child, depth + 1)

    def _split_path(self, path):
        """Split the path into parts, ignoring leading/trailing slashes."""
        return [part for part in path.strip("/").split("/") if part]

    def _parse_query_string(self, query_string):
        """Parse a query string into a dictionary of key-value pairs."""
        return dict(urllib.parse.parse_qsl(query_string))


NOT_FOUND = '404 Not Found'
NOT_ALLOWD = '405 Method Not Allowed'
PLAIN_TEXT = ('Content-Type', 'text/plain')


class Request:
    """A thin wrapper around environ"""

    def __init__(self, environ):
        self._environ = environ

    def __get__(self, key):
        self._environ[key.upper()]


class PyPette:
    """
    A pico WSGI Application framework with API inspired by Bottle.

    There is No HTTPRequest Object and No HTTPResponse object.
    """

    def __init__(self, json_encoder=None, template_path="views"):
        self.resolver = Router()
        self.json_encoder = json_encoder
        self.templates = TemplateEngine(TemplateLoader(template_path))

    def __call__(self, environ, start_response):
        try:
            callback, path_params, query = self.resolver.get(
                    environ.get('PATH_INFO'),
                    environ.get('REQUEST_METHOD'))

        except (NoPathFoundError, NoHandlerError):
            start_response(NOT_FOUND, [PLAIN_TEXT])
            return [NOT_FOUND.encode('utf-8')]

        except MethodMisMatchError:
            start_response(NOT_ALLOWD,
                           [PLAIN_TEXT])
            return [NOT_ALLOWD.encode('utf-8')]

        request = Request(environ)
        response = callback(request, *path_params, **query)

        if isinstance(response, dict):
            response = json.dumps(response, cls=self.json_encoder)
            headers = [('Content-Type', 'application/json')]
        else:
            headers = [PLAIN_TEXT]

        headers.append(('Content-Length', str(len(response))))
        start_response('200 OK', headers)
        return [response.encode('utf-8')]

    def add_route(self, path, callable, method='GET'):
        self.resolver.add_route(path, callable, method)

    def route(self, path, method='GET'):
        def decorator(wrapped):
            self.resolver.add_route(path, wrapped, method)
            return wrapped

        return decorator


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    from datetime import datetime, date

    class DateTimeISOEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return super().default(obj)

    app = PyPette(json_encoder=DateTimeISOEncoder)

    def hello(request):
        return "hello world"

    @app.route("/hello/:name")
    def hello_name(request, name):
        return f"hello {name}"

    @app.route("/api/")
    def hello_json(request):
        return {"something": "you can json serialize ...",
                "today is": date.today(), "now": datetime.now()}

    @app.route('/fancy')
    def view_with_template(request):
        return app.templates.load('base.html').render({
            "user_name": "Admin",
            "is_admin": True,
            "hobbies": ["Reading", "Cooking", "Cycling"],
            "current_year": 2024,
            "format_price": lambda x: x.upper(),
            })

    app.add_route("/", hello)

    app.resolver.print_trie()
    httpd = make_server('', 8000, app)
    print("Serving on port 8000...")

    # Serve until process is killed
    httpd.serve_forever()
