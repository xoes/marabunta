# -*- coding: utf-8 -*-
# Copyright 2016-2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


from io import StringIO

from marabunta.config import Config
from marabunta.parser import YamlParser, YAML_EXAMPLE


def test_parse_yaml_example():
    file_example = StringIO(YAML_EXAMPLE)
    config = Config(None,
                    'test')
    constructor = YamlParser(config)
    constructor.load_from_buffer(file_example)
    migration = constructor.parse()
    assert len(migration.versions) == 4
