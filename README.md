# charm-k8s-nagios

## Description

Nagios is a monitoring and management system for hosts, services, and networks.

This charm initially implements the monitoring of hosts when related to the
[nrpe](https://jaas.ai/nrpe) charm.

## Developing

Clone this repository and then create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

Install microk8s as described on [https://microk8s.io](https://microk8s.io)

Install charmcraft:

    sudo snap install charmcraft

Install juju:

    sudo snap install juju --classic

In order to test the [nrpe](https://jaas.ai/nrpe) relation, it is needed to have
a second cloud. The easyest way to do that is by bootstrapping an LXD juju
controller:

Install LXD:

    snap install lxd

Configure LXD:

    newgrp lxd
    sudo adduser $USER lxd
    lxd init --auto
    lxc network set lxdbr0 ipv6.address none

Bootstrap juju on LXD:

    juju bootstrap localhost lxd


Now, add the microk8s cloud to the the juju controller:

    juju add-k8s micro --controller lxd


And add a *development* model to the microk8s cloud:

    juju add-model development micro

At this time you should have a *default* model on LXD and a *development* model
on microk8s:

     $ juju models
     Controller: lxd
     
     Model         Cloud/Region         Type        Status     Machines  Units  Access  Last connection
     controller    localhost/localhost  lxd         available         1      -  admin   just now
     default       localhost/localhost  lxd         available         1      2  admin   3 hours ago
     development*  micro/localhost      kubernetes  available         0      1  admin   3 hours ago


### Testing environment

To build a testing environment, start deploying ubuntu and nrpe on the *default* model:

     juju switch default
     juju deploy ubuntu
     juju deploy nrpe

Add the nrpe - ubuntu relation:

     juju add-relation ubuntu nrpe

Switch to the *development* model:

    juju switch development

"Pack" the charm:

    charmcraft pack

And then, deploy the nagios-k8s charm:

    juju deploy ./nagios-k8s.charm --resource nagios-image=msmarcal/nagios nagios

Offer the monitors relation

    juju offer nagios:monitors

Relate an deployed nrpe charm from the *default* model to nagios:

    juju switch default
    juju add-relation nrpe admin/deployment.nagios


## Roadmap

* [ ] Add the relation-departed observation
* [ ] Implement the config-changed observation and the related configurations
* [ ] Add the apache2 service to pebble
* [ ] Add the postfix service to pebble
