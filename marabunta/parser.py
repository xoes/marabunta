# -*- coding: utf-8 -*-
# Copyright 2016-2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import print_function


import yaml

from .exception import ParseError, ConfigurationError
from .model import Migration, MigrationOption, Version, Operation
from .database import Database

YAML_EXAMPLE = u"""
migration:
  options:
    # --workers=0 --stop-after-init --no-xmlrpc are automatically added
    # This options are overriden by corresponding command line arguments
    odoo_cmd: odoo
    odoo_args: --log-level=debug
  versions:
    - version: 0.0.1
      operations:
        pre:  # executed before 'addons'
          - echo 'pre-operation'
        post:  # executed after 'addons'
          - anthem songs::install
      addons:
        upgrade:  # executed with -u flag ...
          - base
        install:  # executed with -i flag ...
          - document
        # remove:  # uninstalled with a python script
      modes:
        prod:
          operations:
            pre:
              - echo 'pre-operation executed only when the mode is prod'
            post:
              - anthem songs::load_production_data
        demo:
          operations:
            post:
              - anthem songs::load_demo_data
          addons:
            upgrade:
              - demo_addon

    - version: 0.0.2
      # nothing to do

    - version: 0.0.3
      operations:
        pre:
          - echo 'foobar'
          - ls
          - bin/script_test.sh
        post:
          - echo 'post-op'

    - version: 0.0.4
      addons:
        upgrade:
          - popeye

"""


class YamlParser(object):

    def __init__(self, config, parsed=None):
        self.config = config
        self.parsed = parsed or None

    def load_from_buffer(self, fp):
        """Load parsed YAML from a file pointer."""
        self.parsed = yaml.safe_load(fp)

    def load_from_file(self, filename):
        """Load parsed YAML from a filename."""
        with open(filename, 'rU') as fh:
            self.load_from_buffer(fh)

    def check_dict_expected_keys(self, expected_keys, current, dict_name):
        """ Check that we don't have unknown keys in a dictionary.

        It does not raise an error if we have less keys than expected.
        """
        if not isinstance(current, dict):
            raise ParseError(u"'{}' key must be a dict".format(dict_name),
                             YAML_EXAMPLE)
        expected_keys = set(expected_keys)
        current_keys = {key for key in current}
        extra_keys = current_keys - expected_keys
        if extra_keys:
            message = "u{}: the keys {} are unexpected. (allowed keys: {})"
            raise ParseError(
               message.format(dict_name,
                              list(extra_keys),
                              list(expected_keys)),
               YAML_EXAMPLE
            )

    def parse(self):
        """Check input and return a :class:`Migration` instance."""
        if not self.parsed:
            raise ConfigurationError(u"no marabunta yaml supplied")
        if not self.parsed.get('migration'):
            raise ParseError(u"'migration' key is missing", YAML_EXAMPLE)
        self.check_dict_expected_keys(
            {'options', 'versions'}, self.parsed['migration'], 'migration',
        )
        return self._parse_migrations()

    def _parse_migrations(self):
        """Build a :class:`Migration` instance."""
        migration = self.parsed['migration']
        options = self._parse_options(migration)
        versions = self._parse_versions(migration, options)
        return Migration(versions)

    def _parse_options(self, migration):
        options = migration.get('options') or {}
        odoo_cmd = self.config.odoo_cmd or options.get('odoo_cmd')
        odoo_args = self.config.odoo_args or options.get('odoo_args') or ''
        odoo_addons_path = (
          self.config.odoo_addons_path or
          options.get('odoo_addons_path') or '')
        odoo_dsn = Database(self.config).dsn()
        return MigrationOption(odoo_cmd=odoo_cmd,
                               odoo_args=odoo_args.split(),
                               odoo_dsn=odoo_dsn,
                               odoo_addons_path=odoo_addons_path)

    def _parse_versions(self, migration, options):
        versions = migration.get('versions') or []
        if not isinstance(versions, list):
            raise ParseError(u"'versions' key must be a list", YAML_EXAMPLE)
        return [self._parse_version(version, options) for version in versions]

    def _parse_operations(self, version, operations, mode=None):
        self.check_dict_expected_keys(
            {'pre', 'post'}, operations, 'operations',
        )
        for operation_type, commands in operations.items():
            if not isinstance(commands, list):
                raise ParseError(u"'%s' key must be a list" %
                                 (operation_type,), YAML_EXAMPLE)
            for command in commands:
                version.add_operation(
                    operation_type,
                    Operation(command),
                    mode=mode,
                )

    def _parse_addons(self, version, addons, mode=None):
        self.check_dict_expected_keys(
            {'upgrade', 'install', 'remove'}, addons, 'addons',
        )
        upgrade = addons.get('upgrade') or []
        if upgrade:
            if not isinstance(upgrade, list):
                raise ParseError(u"'upgrade' key must be a list", YAML_EXAMPLE)
            version.add_upgrade_addons(upgrade, mode=mode)
        install = addons.get('install') or []
        if install:
            if not isinstance(install, list):
                raise ParseError(u"'install' key must be a list", YAML_EXAMPLE)
            version.add_install_addons(install, mode=mode)
        remove = addons.get('remove') or []
        if remove:
            if not isinstance(remove, list):
                raise ParseError(u"'remove' key must be a list", YAML_EXAMPLE)
            version.add_remove_addons(remove, mode=mode)

    def _parse_version(self, parsed_version, options):
        self.check_dict_expected_keys(
            {'version', 'operations', 'addons', 'modes'},
            parsed_version, 'versions',
        )
        number = parsed_version.get('version')
        version = Version(number, options)

        # parse the main operations and addons
        operations = parsed_version.get('operations') or {}
        self._parse_operations(version, operations)

        addons = parsed_version.get('addons') or {}
        self._parse_addons(version, addons)

        # parse the modes operations and addons
        modes = parsed_version.get('modes', {})
        if not isinstance(modes, dict):
            raise ParseError(u"'modes' key must be a dict", YAML_EXAMPLE)
        for mode_name, mode in modes.items():
            self.check_dict_expected_keys(
                {'operations', 'addons'}, mode, mode_name,
            )
            mode_operations = mode.get('operations') or {}
            self._parse_operations(version, mode_operations, mode=mode_name)

            mode_addons = mode.get('addons') or {}
            self._parse_addons(version, mode_addons, mode=mode_name)

        return version
