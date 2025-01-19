"""
PyPette is a tiny WSGI framework for building applications in all sizes.
It aims to be simple to understand and to extend.

Copyright (c) 2024-2025, Oz Tiram.
License: MIT (see LICENSE for details)
"""
from __future__ import annotations

import base64, email, hashlib, hmac, http.cookies, http, io, mimetypes, json, pickle, re, os, time, traceback, urllib.parse, wsgiref

from email.parser import HeaderParser

PLAIN_TEXT = ('Content-Type', 'text/plain')


class TempliteSyntaxError(ValueError):
    pass

class TempliteValueError(ValueError):
    pass

class CodeBuilder:
    def __init__(self, indent: int = 0) -> None:
        self.code: list[str | CodeBuilder] = []
        self.indent_level = indent

    def __str__(self) -> str:
        return "".join(str(c) for c in self.code)

    def add_line(self, line: str) -> None:
        self.code.extend([" " * self.indent_level, line, "\n"])

    def add_section(self) -> CodeBuilder:
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def indent(self) -> None:
        self.indent_level += 4

    def dedent(self) -> None:
        self.indent_level -= 4

    def get_globals(self,
                    globals_dict: dict[str, Any] = None) -> dict[str, Any]:
        # Ensure the indentation level is back to zero
        assert self.indent_level == 0

        # Convert the code to a single string
        python_source = str(self)

        # Prepare the global namespace for execution
        global_namespace = globals_dict or {}
        exec(python_source, global_namespace)
        return global_namespace


class TemplateLoader:
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
    """A simple template renderer, now integrated with TemplateLoader for {% include %}."""
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
                        # Add a placeholder for dynamic inclusion at render time
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
        self._render_function = code.get_globals({"Templite": Templite, "loader": loader})["render_function"]  # noqa

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


class QueryDict:
    """
    Simulates a dict-like object for query parameters.

    Because HTTP allows for query strings to provide the same name for a
    parameter more than once, this object smoothes over the day-to-day usage
    of those queries.

    You can act like it's a plain `dict` if you only need a single value.

    If you need all the values, `QueryDict.getlist` & `QueryDict.setlist`
    are available to expose the full list.
    """
    def __init__(self, data=None):
        self._data = data

        if self._data is None:
            self._data = {}

    def __str__(self):
        return "<QueryDict: {} keys>".format(len(self._data))

    def __repr__(self):
        return str(self)

    def __iter__(self):
        return iter(self._data)

    def __contains__(self, name):
        return name in self._data

    def __getitem__(self, name):
        values = self.getlist(name)
        return values[0]

    def __setitem__(self, name, value):
        self._data.setdefault(name, [])
        self._data[name][0] = value

    def get(self, name, default=None):
        """
        Tries to fetch a value for a given name.

        If not found, this returns the provided `default`.

        Args:
            name (str): The name of the parameter you'd like to fetch
            default (bool, defaults to `None`): The value to return if the
                `name` isn't found.

        Returns:
            Any: The found value for the `name`, or the `default`.
        """
        try:
            return self[name]
        except KeyError:
            return default

    def getlist(self, name):
        """
        Tries to fetch all values for a given name.

        Args:
            name (str): The name of the parameter you'd like to fetch

        Returns:
            list: The found values for the `name`.

        Raises:
            KeyError: If the `name` isn't found
        """
        if name not in self._data:
            raise KeyError("{} not found".format(name))

        return self._data[name]

    def setlist(self, name, values):
        """
        Sets all values for a given name.

        Args:
            name (str): The name of the parameter you'd like to fetch
            values (list): The list of all values

        Returns:
            None
        """
        self._data[name] = values

    def keys(self):
        """
        Returns all the parameter names.

        Returns:
            list: A list of all the parameter names
        """
        return self._data.keys()

    def items(self):
        """
        Returns all the parameter names & values.

        Returns:
            list: A list of two-tuples. The parameter names & the *first*
                value for that name.
        """
        results = []

        for key, values in self._data.items():
            if len(values) < 1:
                results.append((key, None))
            else:
                results.append((key, values[0]))

        return results


class StreamingMultipartParser:

    def __init__(self, content_type, max_memory_size=1024*1024):
        self.boundary = self._get_boundary(content_type)
        self.max_memory_size = max_memory_size
        
    def _get_boundary(self, content_type):
        match = re.search(r'boundary=([^;]+)', content_type)
        return match.group(1).encode('utf-8') if match else None

    def parse_stream(self, stream):
        print("Starting to parse stream")
        if not self.boundary:
            return {}, {}

        data = stream.read()
        parts = data.split(b'--' + self.boundary)
        files = {}
        form_data = {}

        for part in parts[1:-1]:  # Skip first empty and last boundary
            if b'\r\n\r\n' not in part:
                continue

            headers_raw, content = part.split(b'\r\n\r\n', 1)
            headers_str = headers_raw.decode('utf-8').strip()

            name = None
            filename = None
            for line in headers_str.splitlines():
                if line.startswith('Content-Disposition:'):
                    for param in line.split(';')[1:]:
                        if '=' in param:
                            key, value = param.strip().split('=', 1)
                            value = value.strip('"')
                            if key == 'name':
                                name = value
                            elif key == 'filename':
                                filename = value

            if filename and name:
                files[name] = {
                    'filename': filename,
                    'content': content.strip(b'\r\n'),
                    'content-type': 'application/octet-stream'
                }
            elif name:
                form_data[name] = content.strip(b'\r\n').decode('utf-8')

        return files, form_data
        
    def _parse_headers(self, header_data):
        parser = HeaderParser()
        return parser.parsestr(header_data.decode('utf-8'))
        
    def _get_content_params(self, headers):
        content_disposition = headers.get('Content-Disposition', '')
        params = dict(param.strip().split('=', 1) for param in 
                     content_disposition.split(';')[1:] if '=' in param)
        return (
            params.get('name', '').strip('"'),
            params.get('filename', '').strip('"')
        )


class FileDict:
    def __init__(self):
        self._files = {}
        self._parsed = False
        self._parser = None
        self._stream = None

    def __getitem__(self, key):
        if not self._parsed and self._parser and self._stream:
            self._files, _ = self._parser.parse_stream(self._stream)
            self._parsed = True
        return self._files[key]

    def __contains__(self, key):
        if not self._parsed and self._parser and self._stream:
            self._files, _ = self._parser.parse_stream(self._stream)
            self._parsed = True
        return key in self._files


class HTTPRequest:
    """
    A request object, representing all the portions of the HTTP request.

    Args:
        uri (str): The URI being requested.
        method (str): The HTTP method ("GET|POST|PUT|DELETE|PATCH|HEAD")
        headers (dict, Optional): The received HTTP headers
        body (str, Optional): The body of the HTTP request
        scheme (str, Optional): The HTTP scheme ("http|https")
        host (str, Optional): The hostname of the request
        port (int, Optional): The port of the request
        content_length (int, Optional): The length of the body of the request
        request_protocol (str, Optional): The protocol of the request
        cookies (http.cookies.SimpleCookie, Optional): The cookies sent as
            part of the request.
    """

    def __init__(
        self,
        uri,
        method,
        headers=None,
        body="",
        scheme="http",
        host="",
        port=80,
        content_length=0,
        request_protocol="HTTP/1.0",
        cookies=None,
        files=None,
        environ=None
    ):
        self.raw_uri = uri
        self.method = method.upper()
        self.body = body
        self.scheme = scheme
        self.host = host
        self.port = int(port)
        self.content_length = int(content_length)
        self.request_protocol = request_protocol
        self._cookies = cookies or http.cookies.SimpleCookie()
        self._body_stream = io.BytesIO(body.encode('utf-8') if isinstance(body, str) else body)
        self.COOKIES = {}
        self._environ = environ

        # For caching.
        self._GET, self._POST, self._PUT = None, None, None

        if not headers:
            headers = {}

        # `Headers` is specific about wanting a list of tuples, so just doing
        # `headers.items()` isn't good enough here.
        self.headers = wsgiref.headers.Headers(
            [(k, v) for k, v in headers.items()]
        )

        for key, morsel in self._cookies.items():
            self.COOKIES[key] = morsel.value

        uri_bits = self.split_uri(self.raw_uri)
        domain_bits = uri_bits.get("netloc", ":").split(":", 1)

        self.path = uri_bits["path"]
        self.query = uri_bits.get("query", {})
        self.fragment = uri_bits.get("fragment", "")

        self.files = FileDict()
        if self.content_type().startswith('multipart/form-data'):
            print("Found multipart form request")
            self.files._parser = StreamingMultipartParser(self.content_type())
            self.files._stream = self._body_stream

        if not self.host:
            self.host = domain_bits[0]

        if len(domain_bits) > 1 and domain_bits[1]:
            self.port = int(domain_bits[1])

    def get_cookie(self, key, default=None, secret=None):
        """ return the content of a cookie. to read a `signed cookie`, the
            `secret` must match the one used to create the cookie (see
            :meth:`baseresponse.set_cookie`). if anything goes wrong (missing
            cookie or wrong signature), return a default value. """
        value = self.COOKIES.get(key)
        if secret and value:
            dec = cookie_decode(value, secret) # (key, value) tuple or none
            return dec[1] if dec and dec[0] == key else default
        return value or default

    def __str__(self):
        return "<HttpRequest: {} {}>".format(self.method, self.raw_uri)

    def __repr__(self):
        return str(self)

    def get_status_line(self):
        return f"{self.method} {self.path} {self.request_protocol}"

    def split_uri(self, full_uri):
        """
        Breaks a URI down into components.

        Args:
            full_uri (str): The URI to parse

        Returns:
            dict: A dictionary of the components. Includes `path`, `query`
                `fragment`, as well as `netloc` if host/port information is
                present.
        """
        bits = urllib.parse.urlparse(full_uri)

        uri_data = {
            "path": bits.path,
            "query": {},
            "fragment": bits.fragment,
        }

        # We need to do a bit more work to make the query portion useful.
        if bits.query:
            uri_data["query"] = urllib.parse.parse_qs(
                bits.query, keep_blank_values=True
            )

        if bits.netloc:
            uri_data["netloc"] = bits.netloc

        return uri_data

    @classmethod
    def from_wsgi(cls, environ):
        """
        Builds a new HttpRequest from the provided WSGI `environ`.

        Args:
            environ (dict): The bag of YOLO that is the WSGI environment

        Returns:
            HttpRequest: A fleshed out request object, based on what was
                present.
        """
        headers = {}
        cookies = {}
        non_http_prefixed_headers = [
            "CONTENT-TYPE",
            "CONTENT-LENGTH",
        ]

        for key, value in environ.items():
            mangled_key = key.replace("_", "-")

            if mangled_key == 'HTTP-COOKIE':
                cookies = http.cookies.SimpleCookie()
                cookies.load(value)
            elif mangled_key.startswith("HTTP-"):
                headers[mangled_key[5:]] = value
            elif mangled_key in non_http_prefixed_headers:
                headers[mangled_key] = value

        body = ""
        wsgi_input = environ.get("wsgi.input", io.StringIO(""))
        content_length = environ.get("CONTENT_LENGTH", 0)

        if content_length not in ("", 0):
            # StringIO & the built-in server have this attribute, but things
            # like gunicorn do not. Give it our best effort.
            if not getattr(wsgi_input, "closed", False):
                body = wsgi_input.read(int(content_length))
        else:
            content_length = 0

        return cls(
            uri=wsgiref.util.request_uri(environ),
            method=environ.get("REQUEST_METHOD", 'GET'),
            headers=headers,
            body=body,
            scheme=wsgiref.util.guess_scheme(environ),
            port=environ.get("SERVER_PORT", "80"),
            content_length=content_length,
            request_protocol=environ.get("SERVER_PROTOCOL", "HTTP/1.0"),
            cookies=cookies,
            environ=environ
        )

    def content_type(self):
        """
        Returns the received Content-Type header.

        Returns:
            str: The content-type header or "text/html" if it was absent.
        """
        return self.headers.get("Content-Type", 'text/html')

    def _ensure_unicode(self, body):
        raw_data = urllib.parse.parse_qs(body)
        revised_data = {}

        # `urllib.parse.parse_qs` can be a very BYTESTRING-Y BOI.
        # Ensure all the keys/value are Unicode.
        for key, value in raw_data.items():
            if isinstance(key, bytes):
                key = key.decode("utf-8")

            if isinstance(value, bytes):  # pragma: no cover
                value = value.decode("utf-8")
            elif isinstance(value, (list, tuple)):
                new_value = []

                for v in value:
                    if isinstance(v, bytes):
                        v = v.decode("utf-8")

                    new_value.append(v)

                value = new_value

            revised_data[key] = value

        return revised_data

    @property
    def GET(self):
        """
        Returns a `QueryDict` of the GET parameters.
        """
        if self._GET is not None:
            return self._GET

        self._GET = QueryDict(self.query)
        return self._GET

    @property
    def POST(self):
        """
        Returns a `QueryDict` of the POST parameters from the request body.

        Useless if the body isn't form-encoded data, like JSON bodies.
        """
        if self._POST is not None:
            return self._POST

        self._POST = QueryDict(self._ensure_unicode(self.body))
        return self._POST

    @property
    def PUT(self):
        """
        Returns a `QueryDict` of the PUT parameters from the request body.

        Useless if the body isn't form-encoded data, like JSON bodies.
        """
        if self._PUT is not None:
            return self._PUT

        self._PUT = QueryDict(self._ensure_unicode(self.body))
        return self._PUT

    def is_secure(self):
        """
        Identifies whether or not the request was secure.

        Returns:
            bool: True if the environment specified HTTPs, False otherwise
        """
        return self.scheme == "https"

    def is_json(self):
        """
        Decodes a JSON body if present.

        Returns:
            dict: The data
        """
        return self.content_type() == 'application/json'
        

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
    pass;

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

    def mount(self, prefix, other_router):
        """
        Mount another router's routes under a specified prefix.
        If prefix is empty or None, merges at root level.

        Args:
            prefix (str): The prefix under which to mount the other router's routes
            other_router (Router): The router instance to mount
        """
        def merge_node(current_node, other_node, current_path):
            # Copy the callback and method if this is a terminal node
            if other_node.callback:
                current_node.callback = other_node.callback
                current_node.method = other_node.method

            # Merge all children
            for key, child in other_node.children.items():
                if key not in current_node.children:
                    # For dynamic routes, include the parameter name directly after ":"
                    if key == ":":
                        param_name = child.rule.split("/")[-1][1:]  # Remove the leading ":"
                        display_path = f"{current_path}/:{param_name}"
                    else:
                        display_path = f"{current_path}/{key}" if current_path else f"/{key}"

                    current_node.children[key] = TrieNode(
                        path=display_path,
                        method=child.method
                    )
                    if key == ":":
                        current_node.children[key].is_dynamic = True

                # Recursively merge the child nodes
                merge_node(
                    current_node.children[key],
                    child,
                    current_node.children[key].rule
                )

        # If prefix is None or empty, start from root
        if not prefix:
            merge_node(self.root, other_router.root, "")
            return

        # Clean and split the prefix
        prefix_parts = self._split_path(prefix)

        # Start from root and create/traverse the prefix path
        current_node = self.root
        current_path = ""

        # Create nodes for the prefix path
        for part in prefix_parts:
            if part not in current_node.children:
                child_path = f"{current_path}/{part}" if current_path else f"/{part}"
                current_node.children[part] = TrieNode(path=child_path)
            current_node = current_node.children[part]
            current_path = current_node.rule

        # Merge the other router's trie starting from this point
        merge_node(current_node, other_router.root, current_path)



    def merge(self, other_router):
        """
        Merge another router's routes into this router at the root level.
        Any conflicting routes will be overwritten by the other router's routes.

        Args:
            other_router (Router): The router instance to merge
        """
        self.mount("", other_router)

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

def _lscmp(a, b):
    '''Compares two strings in a cryptographically safe way. Runtime is not affected by length of common prefix.'''
    return not sum(0 if x==y else 1 for x, y in zip(a, b)) and len(a) == len(b)

def _cookie_is_encoded(data):
    """ Return True if the argument looks like a encoded cookie."""
    return data.startswith(b'!') and b'?' in data

def _cookie_encode(name, value, secret, digestmod=None):
    """ Encode and sign a pickle-able object. Return a (byte) string """
    digestmod = digestmod or hashlib.sha256
    msg = base64.b64encode(pickle.dumps([name, value], -1))
    sig = base64.b64encode(hmac.new(secret.encode(), msg, digestmod=digestmod).digest())
    return b'!' + sig + b'?' + msg

def _cookie_decode(data, secret, digestmod=None):
    """ Verify and decode an encoded string. Return an object or None."""
    data = data.encode()
    if _cookie_is_encoded(data):
        sig, msg = data.split(b'?', 1)
        digestmod = digestmod or hashlib.sha256
        hashed = hmac.new(secret.encode(), msg, digestmod=digestmod).digest()
        if _lscmp(sig[1:], base64.b64encode(hashed)):
            dst = pickle.loads(base64.b64decode(msg))
            return dst

class HTTPResponse:
    """
    A response object, to make responding to requests easier.
    """
    def __init__(self, body="", status_code=200, status_line="OK", headers=None, content_type=PLAIN_TEXT):
        self.body = body
        self.status_code = int(status_code)
        self.status_line = status_line
        self.headers = headers or {}
        self.content_type = content_type
        self._cookies = http.cookies.SimpleCookie()
        self.set_header(*self.content_type)

    def __str__(self):
        return "<HTTPResponse: {}>".format(self.status_code)

    def set_header(self, name, value):
        """
        Sets a header on the response.
        Args:
            name (str): The name of the header.
            value (Any): The value of the header.
        """
        self.headers.update({name: value})

    def set_cookie(
        self,
        key,
        value="",
        max_age=None,
        expires=None,
        path="/",
        domain=None,
        secure=False,
        httponly=False,
        samesite=None,
        secert=None
    ):
        """
        Sets a cookie on the response.

        Takes the same parameters as the `http.cookies.Morsel` object from the stdlib.

        Args:
            key (str): The name of the cookie.
            value (Any): The value of the cookie.
            max_age (int, Optional): How many seconds the cookie lives for.
                Default is `None`
                (expires at the end of the browser session).
            expires (str or datetime, Optional): A specific date/time (in
                UTC) when the cookie should expire. Default is `None`
                (expires at the end of the browser session).
            path (str, Optional): The path the cookie is valid for.
                Default is `"/"`.
            domain (str, Optional): The domain the cookie is valid for.
                Default is `None` (only the domain that set it).
            secure (bool, Optional): If the cookie should only be served by
                HTTPS. Default is `False`.
            httponly (bool, Optional): If `True`, prevents the cookie from
                being provided to Javascript requests. Default is `False`.
            samesite (str, Optional): How the cookie should behave under
                cross-site requests. Options are `SAME_SITE_NONE`,
                `SAME_SITE_LAX`, and `SAME_SITE_STRICT`.
                Default is `None`.
        """
        morsel = http.cookies.Morsel()
        if secret:
            encoded_value = _cookie_encode(key, value, secret)
            morsel.set(key, value, encoded_value)
        else:
            morsel.set(key, value, value)

        # Allow setting expiry w/ a `datetime`.
        if hasattr(expires, "strftime"):
            expires = expires.strftime("%a, %-d %b %Y %H:%M:%S GMT")

        # Always update the meaningful params.
        morsel.update({"path": path, "secure": secure, "httponly": httponly})

        # Ensure the max-age is an `int`.
        if max_age is not None:
            morsel["max-age"] = int(max_age)

        if expires is not None:
            morsel["expires"] = expires

        if domain is not None:
            morsel["domain"] = domain

        if samesite:
            # `samesite` is only supported in Python 3.8+.
            morsel["samesite"] = samesite

        self._cookies[key] = morsel

    def delete_cookie(self, key, path="/", domain=None):
        """
        Removes a cookie by expiring it.
        """
        self.set_cookie(key, value="", max_age=0, path=path,domain=domain)


def static_file(request, filename, root, mimetype=True, download=False, charset='UTF-8', etag=None, headers=None):
    """ Open a file in a safe way and return an instance of `HTTPResponse`
        that can be sent back to the client.

        :param filename: Name or path of the file to send, relative to ``root``.
        :param root: Root path for file lookups. Should be an absolute directory
            path.
        :param mimetype: Provide the content-type header (default: guess from
            file extension)
        :param download: If True, ask the browser to open a `Save as...` dialog
            instead of opening the file with the associated program. You can
            specify a custom filename as a string. If not specified, the
            original filename is used (default: False).
        :param charset: The charset for files with a ``text/*`` mime-type.
            (default: UTF-8)
        :param etag: Provide a pre-computed ETag header. If set to ``False``,
            ETag handling is disabled. (default: auto-generate ETag header)
        :param headers: Additional headers dict to add to the response.

        While checking user input is always a good idea, this function provides
        additional protection against malicious ``filename`` parameters from
        breaking out of the ``root`` directory and leaking sensitive information
        to an attacker.

        Read-protected files or files outside of the ``root`` directory are
        answered with ``403 Access Denied``. Missing files result in a
        ``404 Not Found`` response. Conditional requests (``If-Modified-Since``,
        ``If-None-Match``) are answered with ``304 Not Modified`` whenever
        possible. ``HEAD`` and ``Range`` requests (used by download managers to
        check or continue partial downloads) are also handled automatically.
    """
    root = os.path.join(os.path.abspath(root), '')
    filename = os.path.abspath(os.path.join(root, filename.strip('/\\')))
    headers = headers.copy() if headers else {}
    getenv = request._environ.get
    if not os.path.exists(filename) or not os.path.isfile(filename):
        return HTTPResponse("File does not exist.", 404, "File not found")
    if not os.access(filename, os.R_OK) or not filename.startswith(root):
        return HTTPError("Permission denied", 403, "Permission denied")

    if mimetype:
        name = download if isinstance(download, str) else filename
        mimetype, encoding = mimetypes.guess_type(name)
        if encoding == 'gzip':
            mimetype = 'application/gzip'
        elif encoding: # e.g. bzip2 -> application/x-bzip2
            mimetype = 'application/x-' + encoding

    if charset and mimetype and 'charset=' not in mimetype \
        and (mimetype[:5] == 'text/' or mimetype == 'application/javascript'):
        mimetype += '; charset=%s' % charset

    if mimetype:
        headers['Content-Type'] = mimetype

    if download:
        download = os.path.basename(filename)
        download = download.replace('"','')
        headers['Content-Disposition'] = 'attachment; filename="%s"' % download

    stats = os.stat(filename)
    headers['Content-Length'] = clen = str(stats.st_size)
    headers['Last-Modified'] = email.utils.formatdate(stats.st_mtime, usegmt=True)
    headers['Date'] = email.utils.formatdate(time.time(), usegmt=True)

    if etag is None:
        etag = '%d:%d:%d:%s:%s' % (stats.st_dev, stats.st_ino, stats.st_mtime,
                                   clen, filename)
        etag = hashlib.sha1(etag.encode()).hexdigest()
    else:
        headers['ETag'] = etag
        check = getenv('HTTP_IF_NONE_MATCH')
        if check and check == etag:
            return HTTPResponse(status=304, **headers)

    if (ims := getenv('HTTP_IF_MODIFIED_SINCE')):
        if (parsed_ims := parse_date(ims.split(";")[0].strip())) is not None and parsed_ims >= int(stats.st_mtime):
            return HTTPResponse(status=304, **headers)

    body = '' if request.method == 'HEAD' else open(filename, 'rb')
    return HTTPResponse(body.read(), 200, headers=headers, content_type=('Content-Type', mimetype))


class Pipeline:
    """
    Pipeline supports both simple callables (like decorators) and objects with `setup` and `apply` methods.

    Usage:
    pipeline = Pipeline([plugin1, plugin2, callable_decorator, plugin3])
    wrapped_function = pipeline(original)
    result = wrapped_function(request, *args, **kwargs)
    """
    def __init__(self, plugins):
        self.plugins = plugins
        for plugin in self.plugins:
            if hasattr(plugin, "setup") and callable(plugin.setup):
                plugin.setup()  # Call setup if the plugin is an object with a setup method

    def __call__(self, func):
        # Apply all plugins (either callables or objects) to the function
        for plugin in reversed(self.plugins):
            if hasattr(plugin, "apply") and callable(plugin.apply):
                func = plugin.apply(func)  # Use the plugin's apply method
            elif callable(plugin):
                func = plugin(func)  # Treat as a simple decorator
            else:
                raise TypeError(f"Invalid plugin: {plugin}. Must be callable or have an 'apply' method.")
        return func

def httpstatus_as_str(status):
    """
    >>> httpstatus_as_str("NOT_FOUND")
    '404 Not Found'
    """
    return " ".join([str(getattr(getattr(http.HTTPStatus, status), x))
                     for x in ["value", "phrase"]])


class PyPette:
    """
    A pico WSGI Application framework with an API inspired by Bottle.
    """
    def __init__(self, json_encoder=None, template_path="views", plugins=None):
        self.resolver = Router()
        self.json_encoder = json_encoder
        self.templates = TemplateEngine(TemplateLoader(template_path))
        self.plugin_manager = Pipeline(plugins or [])

    def _process_request(self, env: dict, start_response) -> HTTPRequest:
        handler, args, query = self.resolver.get(env['PATH_INFO'], env['REQUEST_METHOD'])
        return handler, args, query, HTTPRequest.from_wsgi(env)

    def __call__(self, env, start_response):
        body, headers, status, err = b'', [], '200 OK', None
        try:
            self.before_request(env)
            handler, args, query, request = self._process_request(env, start_response)
            response = handler(request, *args, **query)
            self.after_request(request, response)
            if isinstance(response, dict):
                body = json.dumps(response, cls=self.json_encoder).encode()
                headers = [('Content-Type', 'application/json')]
            elif isinstance(response, HTTPResponse):
                headers = [(k, v) for k, v in response.headers.items()]
                possible_cookies = response._cookies.output()
                if possible_cookies:
                    for line in possible_cookies.splitlines():
                        headers.append(tuple(line.split(": ", 1)))

                if hasattr(response.body, 'encode'):
                    body = response.body.encode()
                else:
                    body = response.body
                status = f"{response.status_code} {response.status_line}"
            else:
                headers = [('Content-Type', 'text/html')]
                body = response.encode()
        except (NoPathFoundError, NoHandlerError):
            status, headers, body = self.handle_404()
        except MethodMisMatchError:
            status, headers, body = self.handle_405()
        except Exception as err:
            status, headers, body = self.handle_exception(err)
        finally:
            try:
                self.after_request(env)
            except Exception as err:
                msg = "Error encoutered in after_request: {traceback.print_exception(err)})"
                body += msg.encode()
                print(msg)

                status, headers, body = self.handle_exception(err)

            headers.append(('Content-Length', str(len(body))))
            start_response(status, headers)
            if isinstance(body, str):
                body = body.encode('utf-8')
            return [body]

    def add_route(self, path, callable, method='GET'):
        wrapped=self.plugin_manager(callable)
        self.resolver.add_route(path, wrapped, method)

    def route(self, path, method='GET'):
        def decorator(wrapped):
            self.add_route(path, wrapped, method)
            return wrapped

        return decorator

    def mount(self, prefix, app):
        self.resolver.mount(prefix, app.resolver)

    def install(self, plugin):
        """Add a plugin to the list of plugins and prepare it for being
           applied to all routes of this application. A plugin may be a simple
           decorator or an object that implements the :class:`Plugin` API.
        """
        if hasattr(plugin, 'setup'): plugin.setup(self)
        if not callable(plugin) and not hasattr(plugin, 'apply'):
            raise TypeError("Plugins must be callable or implement .apply()")
        self.plugin_manager.plugins.append(plugin)
        return plugin

    def before_request(self, env):
        """This method is for the user to override.
        Executed once before each request. The request context is available,
        but no routing has happened yet."""
        pass

    def after_request(self, env):
        """This method is for the user to override.
        Executed once after each request regardless of its outcome."""
        pass

    def handle_404(self):
        """Override this to show a more sophisticated 404 page"""
        status = httpstatus_as_str("NOT_FOUND")
        headers = [PLAIN_TEXT]
        body = status.encode('utf-8')
        return status, headers, body

    def handle_405(self):
        """Override this to show a more sophisticated 405 page"""
        status = httpstatus_as_str("METHOD_NOT_ALLOWED")
        headers = [PLAIN_TEXT]
        body = status.encode('utf-8')
        return status, headers, body

    def handle_exception(self, exception):
        """Override this to show a more sophisticated error page"""
        print("In handle_exception")
        if os.getenv("PYPETTE_DEBUG"):
            body = " ".join(traceback.format_exception(exception))
        else:
            body = "Something went awefully wrong"

        status = httpstatus_as_str("INTERNAL_SERVER_ERROR")
        headers = [PLAIN_TEXT]
        return status, headers, body
