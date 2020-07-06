.. # Links
.. _Apache 2.0: https://github.com/turbonomic/vmt-connect/blob/master/LICENSE
.. _arbiter: https://pypi.org/project/arbiter/
.. _CPython: http://www.python.org/
.. _PyPi: http://pypi.org/
.. _Turbonomic: https://www.turbonomic.com
.. _vmt-connect: https://pypi.org/project/vmtconnect/

===============
Getting Started
===============

About
=====

*vmt-report* is a reporting helper library for the *vmt-connect* API library. In
short, this package adds Turbonomic specific handlers for the `arbiter`_ data
handling package. This enabled `Turbonomic`_ API calls to be easily combined and
manipulated into standardized output formats such as CSV, and JSON for data
export or simple reporting needs.


Installation
============

.. code:: bash

   pip install vmtreport


Requirements
============

In order to use vmt-report you will need to be running a supported version of
Python. All dependent modules should be resolved automatically by pip.

* Python:

  - CPython_ >= 3.5

* vmt-connect_ >= 3.2.6

* arbiter_ >= 1.1.0

* Turbonomic_

  - Classic >= 5.9
  - XL >= 7.21


Contributors
============

Author:
  * R.A. Stern

Bug fixes and QA:
  * Ray Mileo


License
=======

*vmt-report* is distributed under the `Apache 2.0`_ software license, which may
also be obtained from the Apache Software Foundation, http://www.apache.org/licenses/LICENSE-2.0
