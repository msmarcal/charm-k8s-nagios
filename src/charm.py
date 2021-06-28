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
from ops.pebble import ServiceStatus

from pynag import Model

logger = logging.getLogger(__name__)

MAIN_NAGIOS_DIR = "/etc/nagios4"
MAIN_NAGIOS_CFG = "/etc/nagios4/nagios.cfg"
CHARM_CFG_PATH = "/etc/nagios4/conf.d"
PLUGIN_PATH = "/usr/lib/nagios/plugins"
EXTRA_CFG = "/etc/nagios4/conf.d/extra.cfg"

class K8SNagiosCharm(CharmBase):

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.nagios_pebble_ready, self._on_nagios_pebble_ready)

        # -- config changed observation
        # self.framework.observe(self.on.config_changed, self._on_config_changed)

        # -- monitors relation observation
        self.framework.observe(self.on["monitors"].relation_changed, self._on_monitors_changed)
        self.framework.observe(self.on["monitors"].relation_departed, self._on_monitors_departed)

        # self._stored.set_default(extraconfig=[])

    def _on_nagios_pebble_ready(self, event):
        """Define and start a workload using the Pebble API."""
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
        # Define an initial Pebble layer configuration
        pebble_layer = {
            "summary": "nagios layer",
            "description": "pebble config layer for nagios",
            "services": {
                "nagiossvc": {
                    "override": "replace",
                    "summary": "nagios service",
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


    def _restart_nagios(self):
        container = self.unit.get_container("nagios")

        try:
            status = container.get_service("nagiossvc")
        except:
            return

        if status.current == ServiceStatus.ACTIVE:
            container.stop("nagiossvc")

        container.start("nagiossvc")



    # def _on_config_changed(self, _):
    #     """Changed extraconfig configuration."""
    #     container = self.unit.get_container("nagios")
    #     current = self.config["extraconfig"]
    #     if current not in self._stored.extraconfig:
    #         logger.info("found a new extraconfig: [%r]", current)
    #         self._stored.extraconfig.append(current)
    #         container.push(EXTRA_CFG, current)
    #     if current == "" and os.path.isfile(EXTRA_CFG):
    #         logger.info("Removing {}...".format(EXTRA_CFG))
    #         container.remove_path(EXTRA_CFG)


    def _on_monitors_changed(self, event: EventBase):
        """Changed monitors relation"""
        container = self.unit.get_container("nagios")
        remote_data = event.relation.data[event.unit]

        try:
            hostname = remote_data['target-id']
        except KeyError:
            return

        host_filename = CHARM_CFG_PATH + "/{}.cfg".format(hostname)

        # Add the new host
        host = Model.Host()
        host.set_filename(host_filename)
        host.set_attribute("host_name", hostname)
        host.set_attribute("use", "generic-host")
        host.set_attribute("address", remote_data['ingress-address'])
        host.set_attribute("max_check_attempts", 5)
        host.set_attribute("check_period", "24x7")
        host.set_attribute("contact_groups", "admins")
        host.set_attribute("notification_options", "d,u,r")
        host.set_attribute("notification_interval", 30)
        host.set_attribute("notification_period", "24x7")
        # Adding the ubuntu icon image definitions to the host.
        host.set_attribute("icon_image", "base/ubuntu.png")
        host.set_attribute("icon_image_alt", "Ubuntu Linux")
        host.set_attribute("vrml_image", "ubuntu.png")
        host.set_attribute("statusmap_image", "base/ubuntu.gd2")

        # Add the services
        checks = json.loads(remote_data['monitors'].replace("'", "\""))
        services = ""
        service = Model.Service()
        service.set_filename(host_filename)

        for check in checks['monitors']['remote']['nrpe'].values():
            service.set_attribute("host_name", hostname)
            service.set_attribute("use", "generic-service")
            service.set_attribute("check_command", "nrpe_" + check)
            service.set_attribute("service_description", "nrpe_" + check)
            services += str(service)

        # Save the config file
        logger.info("Adding config for {} host".format(hostname))
        container.push(host_filename, str(host) + services)

        self._restart_nagios()


    def _on_monitors_departed(self, event: EventBase):
        """ Monitors relation departed. """
        container = self.unit.get_container("nagios")
        # remote_data = event.relation.data[event.unit]
        remote_data = event.relation.data[event.app]
        logger.info

        try:
            hostname = remote_data['target-id']
            logger.info("----- target-id = {}".format(hostname))
        except KeyError:
            return

        # host_filename = CHARM_CFG_PATH + "/{}.cfg".format(hostname)
        # logger.info("Removing {} configuration.".format(hostname))
        # container.remove_path(host_filename)

        self._restart_nagios()

if __name__ == "__main__":
    main(K8SNagiosCharm)
