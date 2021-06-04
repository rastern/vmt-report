#
# NOTES:
#
import pytest
import warnings

import vmtconnect as vc
import vmtreport.actions as va



SERVER = 'localhost:8000'
SERVER_AUTH = 'dGhpczp0aGF0'



class TestFilterSet:
    sample_basic = {'a': 1, 'b': 2}
    sample_exclude = {'a': 1, 'b': 2, 'scope': 'data'}
    sample_merged = {'a': 1, 'b': 'data', 'c': 3}
    sample_override = {'b': 'data', 'c': 3}

    def test_basic(self):
        filter = va.FilterSet(self.sample_basic)

        assert filter.values == self.sample_basic

    def test_exclusion(self):
        filter = va.FilterSet(self.sample_exclude)

        assert filter.values == self.sample_basic

    def test_merge(self):
        base = va.FilterSet(self.sample_basic)
        filter = va.FilterSet(self.sample_override, base)

        assert filter.values == self.sample_merged


class TestScope:
    default = {'id': 'Market'}
    default_false = {'id': '5'}
    market = {'id': '777777', 'type': 'market'}
    entity = {'id': '73431571655824', 'type': 'entity'}
    group = {'id': '284783189570898', 'type': 'group'}

    @classmethod
    def setup_class(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cls.conn = vc.Connection(SERVER, auth=SERVER_AUTH, ssl=False, disable_hateoas=False)

    def test_default_type(self):
        scope = va.Scope(self.conn, self.default)

        assert isinstance(scope.type, va.ScopeTypes)
        assert scope.type == va.ScopeTypes.MARKET
        assert scope.uuid == 'Market'

    def test_default_type_negative(self):
        scope = va.Scope(self.conn, self.default_false)

        assert not isinstance(scope.type, va.ScopeTypes)
        assert scope.type is None
        assert scope.uuid == '5'

    def test_market_lookup(self):
        scope = va.Scope(self.conn, self.market)

        assert isinstance(scope.type, va.ScopeTypes)
        assert scope.type == va.ScopeTypes.MARKET
        assert scope.uuid == '777777'

    def test_entity_lookup(self):
        scope = va.Scope(self.conn, self.entity)

        assert isinstance(scope.type, va.ScopeTypes)
        assert scope.type == va.ScopeTypes.ENTITY
        assert scope.uuid == '73431571655824'

    def test_group_lookup(self):
        scope = va.Scope(self.conn, self.group)

        assert isinstance(scope.type, va.ScopeTypes)
        assert scope.type == va.ScopeTypes.GROUP
        assert scope.uuid == '284783189570898'

    def test_error(self):
        with pytest.raises(ValueError):
            scope = va.Scope(self.conn, self.default_false, stop_error=True)


class TestActionSet:
    market_scope = {'id': 'Market', 'type': 'market'}
    base_dto = {"startTime": "-7d", "endTime": "-1d"}

    @classmethod
    def setup_class(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cls.conn = vc.Connection(SERVER, auth=SERVER_AUTH, ssl=False, disable_hateoas=False)

    def test_init(self):
        actionset = va.ActionSet(self.conn, self.market_scope)

        assert isinstance(actionset.scope, va.Scope)
        assert actionset.dto is None
        assert actionset.response_filter is None
        assert actionset.stop_error is False

    def test_dto(self):
        dto = va.FilterSet(self.base_dto)
        actionset = va.ActionSet(self.conn, self.market_scope, dto)

        assert actionset.dto is not None

    def test_get_actions(self):
        actionset = va.ActionSet(self.conn, self.market_scope)
        data = actionset.get_actions()

        assert len(data) == 482

    def test_get_actions_response_filter(self):
        resp_filter = ['uuid', 'actionType', 'details', 'target', 'currentValue', 'newValue']
        actionset = va.ActionSet(self.conn, self.market_scope, None, resp_filter)
        data = actionset.get_actions()

        assert len(data) == 482

        for f in resp_filter:
            assert f in data[0]

        assert data[0]['uuid'] == '144268689476992'
        assert data[0]['actionType'] == 'RESIZE'
        assert data[0]['details'] == 'Resize down VMem for Virtual Machine dockervm01.demo.turbonomic.com from 2 GB to 1 GB'

    def test_get_actions_error(self):
        dto = va.FilterSet(self.base_dto)
        actionset = va.ActionSet(self.conn, self.market_scope, dto)

        # post here should fail 404
        with pytest.raises(vc.HTTP400Error):
            data = actionset.get_actions()
