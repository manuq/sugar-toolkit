# Copyright (C) 2006, Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import sys
from optparse import OptionParser

import gobject
import gtk
import dbus
import dbus.service
import dbus.glib

from sugar.activity.bundle import Bundle
from sugar.activity import activityhandle
from sugar import logger

# Work around for dbus mutex locking issue
gobject.threads_init()
dbus.glib.threads_init()

class ActivityFactoryService(dbus.service.Object):
    """D-Bus service that creates new instances of an activity"""

    def __init__(self, service_name, activity_class):
        self._activities = []

        splitted_module = activity_class.rsplit('.', 1)
        module_name = splitted_module[0]
        class_name = splitted_module[1]

        module = __import__(module_name)        
        for comp in module_name.split('.')[1:]:
            module = getattr(module, comp)
        if hasattr(module, 'start'):
            module.start()

        self._module = module
        self._constructor = getattr(module, class_name)
    
        bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(service_name, bus = bus)
        object_path = '/' + service_name.replace('.', '/')
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.method("com.redhat.Sugar.ActivityFactory", in_signature="a{ss}")
    def create(self, handle):
        activity_handle = activityhandle.create_from_dict(handle)
        activity = self._constructor(activity_handle)
        activity.present()

        self._activities.append(activity)
        activity.connect('destroy', self._activity_destroy_cb)

        return activity.window.xid

    def _activity_destroy_cb(self, activity):
        self._activities.remove(activity)

        if hasattr(self._module, 'stop'):
            self._module.stop()

        if len(self._activities) == 0:
            gtk.main_quit()

def run(args):
    """Start the activity factory."""
    parser = OptionParser()
    parser.add_option("-p", "--bundle-path", dest="bundle_path",
                      help="path to the activity bundle")
    (options, args) = parser.parse_args()

    sys.path.insert(0, options.bundle_path)

    bundle = Bundle(options.bundle_path)

    logger.start(bundle.get_name())

    os.environ['SUGAR_BUNDLE_PATH'] = options.bundle_path
    os.environ['SUGAR_BUNDLE_SERVICE_NAME'] = bundle.get_service_name()
    os.environ['SUGAR_BUNDLE_DEFAULT_TYPE'] = bundle.get_default_type()

    factory = ActivityFactoryService(bundle.get_service_name(), args[0])
    gtk.main()