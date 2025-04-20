.. pypette documention documentation master file, created by
   sphinx-quickstart on Tue Jan 21 12:51:58 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

pypette documentation
=================================


.. toctree::
   :maxdepth: 2
   :caption: Contents:


`PyPette` is a nano WSGI framework. It is inspired by `bottle.py`,s but aims
to be even small and more readable. It does so by adding an explicit request
instance to each request handler and replacing the built in RegEx routing with
a Trie based one. In addintion, it's built in template system is not based
on RegEx and has a more Jinja2 like syntax.

PyPette is small, but it will come with a few usefull plugins which are optionally
installable.

 * PyPette Admin - Out of the box HTML views for interacting with databases (a la
   Django's admin).
 * PyPette REST - out of the box REST API for your databases (a la DRF).
 * PyPette OpenAPI - out of the box REST documentation.
