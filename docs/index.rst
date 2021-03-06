:orphan:

.. pyBlueVia documentation master file, created by
   sphinx-quickstart on Fri Jan 18 11:29:03 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

pyBlueVia v\ |version|
======================

.. centered:: A Python wrapper around the BlueVia API

----------------------------------------------

**pyBlueVia** is an :ref:`Apache2 Licensed <apache2>` library, written in Python, for making
easier the usage of `BlueVia <http://bluevia.com>`_ API.

**pyBlueVia** implements an :class:`~.bluevia.Api` class which wraps the BlueVia API,
offering methods for:

* Managing OAuth 2.0 authorization process for APIs which need an *access token*.
* Sending SMS and MMS.
* Asking for the delivery status of sent SMS/MMS.
* Retrieve SMS/MMS sent to your app.
* Parsing notifications (delivery status and incoming SMS/MMS) coming from BlueVia.


.. toctree::
   :hidden:
   :maxdepth: 2
   
   introduction
   user-guide
   api-reference


:ref:`Introduction <introduction>`
----------------------------------

* :ref:`apache2`
* :ref:`install`


:ref:`User Guide <user-guide>`
------------------------------

* :ref:`api-wrapper`
* :ref:`access-token`
* :ref:`sms`
* :ref:`mms`


:ref:`Api Reference <api-reference>`
------------------------------------

* :ref:`api-reference-summary`
* :ref:`api-class`
* :ref:`exceptions`


.. Indices and tables
.. ==================

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

