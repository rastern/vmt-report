.. _arbiter: https://github.com/rastern/arbiter
.. _vmt-connect: https://turbonomic.github.io/vmt-connect/start.html

============================
vmt-report: Reporting Helper
============================

*vmt-report* adds Turbonomic specific handlers for the `arbiter`_ data handling
package. This enabled Turbonomic API calls to be easily combined and manipulated
into standardized output formats such as CSV, and JSON for data export or simple
reporting needs.


Installation
============

.. code-block:: bash

   pip install vmtreport


Usage
=====

*vmt-report* installs the appropriate ``vmtconnect`` and ``credstore`` handlers for
connecting to Turbonomic instances using `vmt-connect`_.
The JSON config controls most of the behavior of *arbiter*, while the

Example Script (example.py)
---------------------------

.. code-block:: python

    # Dump selected fields from all market actions
    import arbiter
    import vmtreport
    import umsg

    # source worker sub-process must accept 3 parameters
    def actions(source, config, logger):
        umsg.log(f"Retrieving data from {config['resource']}", logger=logger)
        res = source.connect().get_actions()
        fields = ['createTime', 'actionType', 'details']
        return [{x: res[x]} for x in res if x in fields]

    if __name__ == '__main__':
      config = arbiter.load('report.config')
      report = arbiter.Process(config, actions)
      report.run()


Example Config (report.config)
------------------------------

.. code-block:: json

  {
    "sources": [
      {
        "handler": "vmtconnect",
        "resource": "https://localhost",
        "authentication": {
          "type": "credstore",
          "credential": "./credential.credstore",
          "keyfile": "./turbo.keyfile"
        }
      }
    ],
    "outputs": [
      {
        "handler": "CSV",
        "resource": "file:/tmp/{timestamp}-actions.csv"
      }
    ],
    "notifications": [
      {
        "handler": "email",
        "on_success": true,
        "on_failure": true,
        "options": {
          "email": {
            "from": ["no-reply@turbonomic.com"],
            "to": ["user@example.com"],
            "subject": "Actions Report for {date}",
            "body": "Wasted Storage Report generated on {timestamp}.",
            "body_error": "Errors happened: {errors}"
          }
        }
      }
    ],
    "logging": {
      "mode": "DEBUG"
    },
    "process_timeout": 60
  }
