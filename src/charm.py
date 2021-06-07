#!/usr/bin/env python3
# Copyright 2021 Marcelo Marcal
# See LICENSE file for licensing details.

import logging
import os
import json

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.framework import EventBase
from ops.main import main
from ops.model import ActiveStatus

from pynag import Model

logger = logging.getLogger(__name__)

MAIN_NAGIOS_DIR = "/etc/nagios4"
MAIN_NAGIOS_CFG = "/etc/nagios4/nagios.cfg"
CHARM_CFG = "/etc/nagios4/conf.d/charm.cfg"
PLUGIN_PATH = "/usr/lib/nagios/plugins"
EXTRA_CFG = "/etc/nagios4/conf.d/extra.cfg"

class K8SNagiosCharm(CharmBase):

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.nagios_pebble_ready, self._on_nagios_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        # -- monitors relation observation
        self.framework.observe(self.on["monitors"].relation_changed, self._on_monitors_changed)

        self._stored.set_default(extraconfig=[])

    def _on_nagios_pebble_ready(self, event):
        """Define and start a workload using the Pebble API."""
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
        # Define an initial Pebble layer configuration
        pebble_layer = {
            "summary": "nagios layer",
            "description": "pebble config layer for nagios",
            "services": {
                "nagios": {
                    "override": "replace",
                    "summary": "nagios",
                    "command": "/usr/sbin/nagios4 /etc/nagios4/nagios.cfg",
                    "startup": "enabled",
                    "environment": {
                        "extraconfig": self.model.config["extraconfig"],
                    },
                }
            },
        }
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("nagios", pebble_layer, combine=True)
        # Autostart any services that were defined with startup: enabled
        container.autostart()
        self.unit.status = ActiveStatus()


    def _on_config_changed(self, _):
        """Changed configuration."""
        container = self.unit.get_container("nagios")
        current = self.config["extraconfig"]
        if current not in self._stored.extraconfig:
            logger.info("found a new extraconfig: [%r]", current)
            self._stored.extraconfig.append(current)
            container.push(EXTRA_CFG, current)
        if current == "" and os.path.isfile(EXTRA_CFG):
            logger.info("Removing {}...".format(EXTRA_CFG))
            container.remove_path(EXTRA_CFG)


    def _on_monitors_changed(self, event: EventBase):
        """Changed monitors relation"""
        container = self.unit.get_container("nagios")
        remote_data = event.relation.data[event.unit]
        hostname = remote_data['target-id']

        # Add the new host
        host = Model.Host()
        host.set_filename(CHARM_CFG)
        host.set_attribute("host_name", hostname)
        host.set_attribute("use", "generic-host")
        # Adding the ubuntu icon image definitions to the host.
        host.set_attribute("icon_image", "base/ubuntu.png")
        host.set_attribute("icon_image_alt", "Ubuntu Linux")
        host.set_attribute("vrml_image", "ubuntu.png")
        host.set_attribute("statusmap_image", "base/ubuntu.gd2")
        host.set_attribute("address", remote_data['ingress-address'])

        # Add the services
        checks = json.loads(remote_data['monitors'].replace("'", "\""))

        services = ""
        service = Model.Service()
        service.set_filename(CHARM_CFG)
        for check in checks['monitors']['remote']['nrpe'].values():
            service.set_attribute("host_name", hostname)
            service.set_attribute("use", "generic-service")
            service.set_attribute("check_command", "check_nrpe_" + check)
            services += str(service)

        # Save the config
        container.push(CHARM_CFG, str(host) + str(services))


if __name__ == "__main__":
    main(K8SNagiosCharm)
