#
# NOTES:
#   Set disable_hateoas=False in all connections
#
import pytest
import warnings

import vmtconnect as vc
import vmtreport.common as common



SERVER = 'localhost:8000'
SERVER_AUTH = 'dGhpczp0aGF0'



html_tag_params = [
    pytest.param('a', 'text', None, None, '<a>text</a>'),
    pytest.param('tr', 'text', None, None, '<tr>text</tr>'),
    pytest.param('a', 'cls', 'simple', None, '<a class="simple">cls</a>'),
    pytest.param('a', 'cls', ['simple'], None, '<a class="simple">cls</a>'),
    pytest.param('a', 'sty', None, 'simple', '<a style="simple">sty</a>'),
    pytest.param('a', 'sty', None, ['simple'], '<a style="simple">sty</a>')
]
html_attr_params = [
    # null tests
    pytest.param(None, None, ''),
    pytest.param('', '', ''),
    # class tests
    pytest.param('class', 'sample', ' class="sample"'),
    pytest.param('class', [None], ''),
    pytest.param('class', ['sample1'], ' class="sample1"'),
    pytest.param('class', [None, None], ''),
    pytest.param('class', ['sample1', 'sample2', 'sample3'], ' class="sample1 sample2 sample3"'),
]
html_attr_delim_params = [
    # null tests
    pytest.param(None, None, None, ''),
    pytest.param('', '', ';', ''),
    # style tests - things with
    pytest.param('style', 'margin: 0.6em', '; ', ' style="margin: 0.6em"'),
    pytest.param('style', ['margin: 0.6em'], '; ', ' style="margin: 0.6em"'),
    pytest.param('style', ['margin: 0.6em', 'background: none #fff', 'sample2', 'sample3'], '; ', ' style="margin: 0.6em; background: none #fff; sample2; sample3"')
]



@pytest.mark.parametrize('tag,data,cls,sty,output', html_tag_params)
def test_html_tag(tag, data, cls, sty, output):
    html = common.html_tag(tag, data, cls, sty)

    assert output == html


@pytest.mark.parametrize('attr, values, output', html_attr_params)
def test_html_attr_no_delim(attr, values, output):
    attribute = common.html_attr(attr, values)

    assert output == attribute


@pytest.mark.parametrize('attr, values, delim, output', html_attr_delim_params)
def test_html_attr_delim(attr, values, delim, output):
    attribute = common.html_attr(attr, values, delim)

    assert output == attribute
