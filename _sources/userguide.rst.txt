.. # Links
.. _API: https://greencircle.vmturbo.com/community/products/pages/documentation
.. _arbiter: https://pypi.org/project/arbiter/
.. _Turbonomic: http://www.turbonomic.com
.. _vmt-connect: https://pypi.org/project/vmtconnect/

==========
User Guide
==========

*vmt-report* provides two handlers for the `arbiter`_ Python package, enabling
`Turbonomic`_ data to be easily utilized in custom data workflows, reports,
and data handling tasks

arbiter
=======

*vmt-report* is an extension to arbiter, providing interfaces to Turbonomic.
A basic understanding of arbiter is necessary to be successful with *vmt-report*,
though one does not need to have mastered the dependency by any means.

The heart of arbiter is the :py:class:`arbiter.Process` class, which consumes
a `configuration <https://arbiter.readthedocs.io/en/latest/userguide.html#configuration>`_
file defining handlers and directives. Basically a config telling the processor
what data to input, and what to output, along with some possible notifications
to send. A minimum working example for converting a CSV file to a JSON file may
look like this:

.. literalinclude:: ./_static/example_1-script.py
  :language: python
  :caption: example.py

.. literalinclude:: ./_static/example_1-report.conf
  :language: json
  :caption: report.conf

Handlers are free to define their own configuration parameters, and the documentation
for the specific handler being used should be consulted for such information.
The two handlers *vmt-report* defines, :py:class:`~vmtreport.GroupedData` and
:py:class:`~vmtreport.Connection`, are documented.

|

Cluster & Group Based Reports
=============================

The :py:class:`~vmtreport.GroupedData` provides basic data processing
capabilities based on groups (including clusters) within Turbonomic. The handler
utilizes a list of groups, and a list of field definitions. Optionally a third
list of sorting parameters may be included. The resultant data is a mapped dataset
represented by an :py:class:`collections.OrderedDict`.

.. literalinclude:: ./_static/example_2-cluster.conf
  :language: json
  :caption: Example cluster based report config

Groups
------

Groups define the scope within Turbonomic to limit data gathering to. Two types of
groups are supported: *cluster* and *group*. Clusters are distinguished because
Turbonomic treats these separate from all other entities internally. When using
the *cluster* type, the default behavior is to use all clusters unless a **names**
filter is provided; when using the type *group* a **names** filter must be provided.
Groups are defined in the **groups** sub-block of the configuration.

:py:attr:`Parameters:`
  :type:  Specifies if the intended scope objects are Turbo groups or clusters.
  :names:  List of names / uuids to limit the scope to.
  :stop_on_error:  If ``True``, non-existent or groups that produce errors will
    be raised as an exception. By default errors are ignored. Default: ``False``

Fields
------

Fields provide *vmt-report* with detailed information regarding which data to
gather, and how to make use of it in the final output. All field definitions
must contain a unique **id**, a valid **type**, and a valid **value**. The **label**
parameter controls if the field is included in final output, thus you may declare
fields as required for use in calculations, that are then excluded from the final
report. This is a critical feature for computed fields, as they themselves cannot
directly reference commodities or properties on entities.

Computed fields permit custom calculations upon report data, storing the data
into the field for use by other computed fields, or for display in the report.
The **value** may contain most any valid python expression that evaluates to a
value; and explicitly excludes the use of assignment operators. Functions may
also be called provided they do not require external input and return a value.
Other fields may be referenced by prefixing the field **id** with a ``$``. All
other field data is populated prior to the processing of computed fields, thus
field order is not typically an issue for computed fields in general. However,
if a computed field references another computed field, the referenced field must
appear earlier in the list than the field referencing it so that the referenced
field is computed before its value is required. Computed fields are evaluated in
sequential order starting at the top of the list.

.. warning::
  *vmt-report* does not check for field order dependency or circular dependency
  errors.

Fields are defined in the **fields** sub-block of the configuration as a list of
dictionaries with the following parameters.

:py:attr:`Parameters:`
  :id:  Unique, user supplied internal identifier for the id. This is used when
    referencing other fields in calculated fields, and the field must contain
    only alphanumeric characters.
  :type:  One of the the defined FieldTypes, as a string literal: commodity,
    computed, property, or string.
  :value:  The value. This differs by type, and is discussed in detail below.
  :label:  Optional. The column header to use in the final output.

Values by type:
  * commodity - colon separated path to the statistical value, prefixed by the
    commodity name.
  * computed - the expression to evaluate
  * property - colon separated path to the entity property
  * string - string literal value which is not interpreted further. An empty string
    is valid.


Sorting
-------

Final output may be sorted using the **sortby** option, by supplying a list of
field **ids**. Multi-level sorting is supported, and proceeds left-to-right in
the field list. Fields are sorted in ascending order by default, and any field
may independently be reversed to descending order by prefixing the **id** with a
``-`` dash.

|

Advanced Use Cases
==================

For use cases that go beyond group level data, or that require special processing
of the data gathering, *vmt-report* supports full customization of both the handler
and worker components.

Connection Handler
------------------

The base handler *vmt-report* provides is the :py:class:`~vmtreport.Connection`.
The handler is responsible for establishing a connection to Turbonomic using the
`vmt-connect`_ module, and returns a :py:class:`vmtconnect.Connection` object.
Coupled with a customer worker process, detailed below, permits complete access
to the Turbonomic API. The handler requires only an authentication directive
and supports any that return either a username and password, or an auth string,
including the **basic**, **auth**, **env**, and *vmt-report* supplied **credstore**.

Credstore Authentication
------------------------

*vmt-report* includes an additional authentication handler for accepting *vmt-connect*
style credentials.

.. literalinclude:: ./_static/example_3-connection.conf
  :language: json
  :caption: Connection handler & credstore authentication

Custom Workers
--------------

A custom worker definition is required to make use of a :py:class:`~vmtreport.Connection`
handler. arbiter natively supports custom worker definitions by passing a function
reference to the :py:class:`arbiter.Process` constructor. All workers are run as
separate processes, and so the function must return data in a mergable format. If
the data requires special attention to merge, the user is responsible for providing
the proper :py:meth:`arbiter.Process.merge_results` overloaded method.

.. literalinclude:: ./_static/example_4-worker.py
  :language: python
  :caption: Custom worker example.
