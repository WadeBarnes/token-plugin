#!/usr/bin/env bash
echo -e "\nENABLED_PLUGINS = ['sovtoken', 'sovtokenfees']" >> /etc/indy/indy_config.py
pip3 install -e sovtoken/
pip3 install -e sovtokenfees/
