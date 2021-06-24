#
# NOTES:
#   Set disable_hateoas=False in all connections
#
import pytest
import warnings

import vmtconnect as vc
import vmtreport.targets as va



SERVER = 'localhost:8000'
SERVER_AUTH = 'dGhpczp0aGF0'



class TestTargets:
    empty_config = {}

    @classmethod
    def setup_class(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cls.conn = vc.Connection(SERVER, auth=SERVER_AUTH, ssl=False, disable_hateoas=False)

    def test_init(self):
        targets = va.Targets(self.conn)

        assert targets.resp_filter is None
        assert targets.stop_error is False

    def test_get(self):
        targets = va.Targets(self.conn, self.empty_config)

        assert len(targets.get()) == 15

    def test_get_targets_response_filter(self):
        resp_filter = ['uuid', 'displayName', 'status', 'lastValidated', 'category', 'type']
        targets = va.Targets(self.conn, resp_filter)
        data = targets.get()

        assert len(data) == 15

        # check all filter fields are valid
        assert len(data[0].keys()) == len(resp_filter)

        for f in resp_filter:
            assert f in data[0]

        # action-base
        assert data[0]['uuid'] == '73645133796016'
        assert data[0]['displayName'] == 'hv19-cluster1.corp.vmturbo.com'
        assert data[0]['status'] == 'Validated'
        assert data[0]['lastValidated'] == '2021-06-09T21:03:08Z'
        assert data[0]['category'] == 'Hypervisor'
        assert data[0]['type'] == 'Hyper-V'
